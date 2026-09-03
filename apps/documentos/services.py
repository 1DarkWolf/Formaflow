import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.candidaturas.models import Candidatura
from apps.candidaturas.selectors import (
    utilizador_pode_consultar_equipa,
    utilizador_pode_editar_candidatura,
    utilizador_pode_operar_candidatura,
)
from apps.organizacoes.selectors import utilizador_e_administrador
from apps.regras.models import ParametroRegra, TipoDocumento

from .models import (
    Documento,
    EstadoDocumento,
    FaseDocumento,
    FicheiroArmazenado,
    RequisitoDocumento,
    SnapshotSubmissao,
    VersaoDocumento,
)
from .storage import eliminar_privado, guardar_privado, validar_pdf

CODIGO_LIMITE_FICHEIRO = "CFG-FICHEIRO-TAMANHO"
MEBIBYTE = 1024 * 1024


def _exigir_edicao(user, candidatura):
    if not utilizador_pode_editar_candidatura(user, candidatura):
        raise PermissionDenied("Não pode alterar os documentos desta candidatura.")


def utilizador_pode_carregar_requisito(user, requirement):
    candidature = requirement.candidatura
    if not candidature.editavel or not user or not user.is_authenticated or not user.is_active:
        return False
    if utilizador_pode_editar_candidatura(user, candidature):
        return True
    profile = getattr(user, "perfil_candidato", None)
    if profile is None:
        return False
    if requirement.beneficiario_id:
        return requirement.beneficiario.candidato_id == profile.pk
    return bool(
        candidature.tipo == Candidatura.Tipo.INDIVIDUAL
        and candidature.titular_candidato_id == profile.pk
    )


def utilizador_pode_substituir_documento(user, document):
    if document.requisito_id:
        return utilizador_pode_carregar_requisito(user, document.requisito)
    candidature = document.candidatura
    if utilizador_pode_editar_candidatura(user, candidature):
        return True
    profile = getattr(user, "perfil_candidato", None)
    return bool(
        profile
        and candidature.editavel
        and user.is_active
        and document.beneficiario_id
        and document.beneficiario.candidato_id == profile.pk
    )


def utilizador_pode_validar_documentos(user, candidatura):
    return bool(
        utilizador_pode_editar_candidatura(user, candidatura)
        and (
            utilizador_e_administrador(user) or utilizador_pode_consultar_equipa(user, candidatura)
        )
    )


def _limite_ficheiro(candidatura):
    if not candidatura.conjunto_regras_id:
        raise ValidationError("A candidatura não tem regras para validar o ficheiro.")
    try:
        parameter = candidatura.conjunto_regras.parametros.get(codigo=CODIGO_LIMITE_FICHEIRO)
    except ParametroRegra.DoesNotExist as error:
        raise ValidationError("O limite de ficheiro não está configurado.") from error
    value = parameter.valor
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError("O limite de ficheiro configurado é inválido.")
    unit = parameter.unidade.strip().upper()
    if unit not in {"MB", "MIB"}:
        raise ValidationError("A unidade do limite de ficheiro não é suportada.")
    return value * MEBIBYTE


def _tipos_necessarios(candidatura):
    codes = {"TITULARIDADE_BANCARIA"}
    if candidatura.tipo == Candidatura.Tipo.EMPRESARIAL:
        codes.add("DOCUMENTO_EMPRESA")
    for beneficiary in candidatura.beneficiarios.all():
        codes.update({"IDENTIFICACAO_CIVIL", "SITUACAO_LABORAL"})
        if beneficiary.situacao_referencia == "DESEMPREGADO":
            codes.add("CURRICULO")
        if beneficiary.participacoes_formacao.exists():
            codes.add("DECLARACAO_FORMADORA")
    return codes


@transaction.atomic
def gerar_checklist_preparacao(*, candidatura_id, utilizador):
    candidatura = (
        Candidatura.objects.select_for_update()
        .select_related("conjunto_regras")
        .prefetch_related("beneficiarios__participacoes_formacao")
        .get(pk=candidatura_id)
    )
    _exigir_edicao(utilizador, candidatura)
    codes = _tipos_necessarios(candidatura)
    types = TipoDocumento.objects.filter(codigo__in=codes, ativo=True).in_bulk(field_name="codigo")
    missing = sorted(codes - types.keys())
    if missing:
        raise ValidationError(
            "Faltam tipos documentais ativos na configuração: " + ", ".join(missing)
        )

    specs = [
        {
            "tipo_documento": types["TITULARIDADE_BANCARIA"],
            "codigo_regra": "RN-FIN-006",
        }
    ]
    if candidatura.tipo == Candidatura.Tipo.EMPRESARIAL:
        specs.append(
            {
                "tipo_documento": types["DOCUMENTO_EMPRESA"],
                "codigo_regra": "RN-DOC-003",
            }
        )
    for beneficiary in candidatura.beneficiarios.all():
        specs.extend(
            (
                {
                    "beneficiario": beneficiary,
                    "tipo_documento": types["IDENTIFICACAO_CIVIL"],
                    "codigo_regra": "RN-DOC-004",
                },
                {
                    "beneficiario": beneficiary,
                    "tipo_documento": types["SITUACAO_LABORAL"],
                    "codigo_regra": (
                        "RN-DOC-005"
                        if beneficiary.situacao_referencia == "DESEMPREGADO"
                        else "RN-DOC-004"
                    ),
                },
            )
        )
        if beneficiary.situacao_referencia == "DESEMPREGADO":
            specs.append(
                {
                    "beneficiario": beneficiary,
                    "tipo_documento": types["CURRICULO"],
                    "codigo_regra": "RN-DOC-005",
                }
            )
        for participation in beneficiary.participacoes_formacao.all():
            specs.append(
                {
                    "beneficiario": beneficiary,
                    "participacao": participation,
                    "tipo_documento": types["DECLARACAO_FORMADORA"],
                    "codigo_regra": "RN-DOC-006",
                }
            )

    created = []
    for spec in specs:
        lookup = {
            "candidatura": candidatura,
            "beneficiario": spec.get("beneficiario"),
            "participacao": spec.get("participacao"),
            "tipo_documento": spec["tipo_documento"],
            "fase": FaseDocumento.PREPARACAO,
        }
        requirement, was_created = RequisitoDocumento.objects.get_or_create(
            **lookup,
            defaults={
                "codigo_regra": spec["codigo_regra"],
                "obrigatorio": True,
                "bloqueante": True,
            },
        )
        if was_created:
            requirement.full_clean()
            created.append(requirement)
    return created


def _guardar_ficheiro_validado(upload, candidature, user):
    validated = validar_pdf(upload, _limite_ficheiro(candidature))
    key = guardar_privado(validated.pop("conteudo"))
    return key, FicheiroArmazenado(
        chave_armazenamento=key,
        estado_upload=FicheiroArmazenado.EstadoUpload.CONCLUIDO,
        estado_seguranca=FicheiroArmazenado.EstadoSeguranca.SEGURO,
        carregado_por=user,
        **validated,
    )


def carregar_para_requisito(
    *, requisito_id, ficheiro, utilizador, titulo="", emitido_em=None, valido_ate=None
):
    requirement = RequisitoDocumento.objects.select_related(
        "candidatura__conjunto_regras",
        "tipo_documento",
        "beneficiario__candidato",
        "participacao",
    ).get(pk=requisito_id)
    if not utilizador_pode_carregar_requisito(utilizador, requirement):
        raise PermissionDenied("Não pode carregar este documento.")
    if requirement.documentos.exists():
        raise ValidationError("Este requisito já tem documento; carregue uma nova versão.")
    key = None
    try:
        key, stored_file = _guardar_ficheiro_validado(ficheiro, requirement.candidatura, utilizador)
        with transaction.atomic():
            requirement = RequisitoDocumento.objects.select_for_update().get(pk=requirement.pk)
            if requirement.documentos.exists():
                raise ValidationError(
                    "Este requisito recebeu um documento noutra sessão; atualize a página."
                )
            stored_file.full_clean()
            stored_file.save()
            document = Documento(
                candidatura=requirement.candidatura,
                beneficiario=requirement.beneficiario,
                participacao=requirement.participacao,
                tipo_documento=requirement.tipo_documento,
                requisito=requirement,
                fase=requirement.fase,
                titulo=titulo.strip(),
                estado_atual=EstadoDocumento.RECEBIDO,
                criado_por=utilizador,
            )
            document.full_clean()
            document.save()
            version = VersaoDocumento(
                documento=document,
                numero=1,
                ficheiro=stored_file,
                carregada_por=utilizador,
                emitido_em=emitido_em,
                valido_ate=valido_ate,
            )
            version.full_clean()
            version.save()
            RequisitoDocumento.objects.filter(pk=requirement.pk).update(
                estado=EstadoDocumento.RECEBIDO,
                atualizado_em=timezone.now(),
            )
        return version
    except Exception:
        if key:
            eliminar_privado(key)
        raise


def substituir_documento(
    *, documento_id, ficheiro, motivo, utilizador, emitido_em=None, valido_ate=None
):
    document = Documento.objects.select_related(
        "candidatura__conjunto_regras",
        "beneficiario__candidato",
        "requisito__beneficiario__candidato",
    ).get(pk=documento_id)
    if not utilizador_pode_substituir_documento(utilizador, document):
        raise PermissionDenied("Não pode substituir este documento.")
    reason = motivo.strip()
    if not reason:
        raise ValidationError("Explique o motivo da substituição.")
    key = None
    try:
        key, stored_file = _guardar_ficheiro_validado(ficheiro, document.candidatura, utilizador)
        with transaction.atomic():
            document = (
                Documento.objects.select_for_update()
                .select_related("requisito")
                .get(pk=document.pk)
            )
            current = document.versoes.select_for_update().get(corrente=True)
            next_number = (document.versoes.aggregate(highest=Max("numero"))["highest"] or 0) + 1
            stored_file.full_clean()
            stored_file.save()
            VersaoDocumento.objects.filter(pk=current.pk).update(
                corrente=False,
                estado_validacao=VersaoDocumento.EstadoValidacao.SUBSTITUIDO,
                motivo_substituicao=reason,
            )
            version = VersaoDocumento(
                documento=document,
                numero=next_number,
                ficheiro=stored_file,
                carregada_por=utilizador,
                emitido_em=emitido_em,
                valido_ate=valido_ate,
            )
            version.full_clean()
            version.save()
            Documento.objects.filter(pk=document.pk).update(
                estado_atual=EstadoDocumento.RECEBIDO,
                atualizado_em=timezone.now(),
            )
            if document.requisito_id:
                RequisitoDocumento.objects.filter(pk=document.requisito_id).update(
                    estado=EstadoDocumento.RECEBIDO,
                    atualizado_em=timezone.now(),
                )
        return version
    except Exception:
        if key:
            eliminar_privado(key)
        raise


def carregar_documento_workflow(
    *,
    candidatura_id,
    tipo_documento,
    ficheiro,
    utilizador,
    titulo="",
    beneficiario=None,
):
    candidature = Candidatura.objects.select_related("conjunto_regras").get(pk=candidatura_id)
    allowed_states = {
        Candidatura.Estado.SUBMETIDA,
        Candidatura.Estado.EM_ANALISE,
        Candidatura.Estado.AGUARDA_ELEMENTOS,
        Candidatura.Estado.APROVADA_AGUARDA_TERMO,
    }
    profile = getattr(utilizador, "perfil_candidato", None)
    beneficiary_scope = bool(
        beneficiario
        and profile
        and beneficiario.candidato_id == profile.pk
        and beneficiario.candidatura_id == candidature.pk
    )
    if candidature.estado_atual not in allowed_states or not (
        utilizador_pode_operar_candidatura(utilizador, candidature) or beneficiary_scope
    ):
        raise PermissionDenied("Não pode guardar documentos de acompanhamento nesta fase.")
    if not tipo_documento.ativo:
        raise ValidationError("O tipo documental selecionado não está ativo.")
    if beneficiario and beneficiario.candidatura_id != candidature.pk:
        raise ValidationError("O beneficiário não pertence à candidatura.")
    key = None
    try:
        key, stored_file = _guardar_ficheiro_validado(ficheiro, candidature, utilizador)
        with transaction.atomic():
            stored_file.full_clean()
            stored_file.save()
            document = Documento(
                candidatura=candidature,
                beneficiario=beneficiario,
                tipo_documento=tipo_documento,
                fase=FaseDocumento.ANALISE,
                titulo=titulo.strip(),
                estado_atual=EstadoDocumento.RECEBIDO,
                criado_por=utilizador,
            )
            document.full_clean()
            document.save()
            version = VersaoDocumento(
                documento=document,
                numero=1,
                ficheiro=stored_file,
                carregada_por=utilizador,
            )
            version.full_clean()
            version.save()
        return version
    except Exception:
        if key:
            eliminar_privado(key)
        raise


@transaction.atomic
def validar_versao(*, versao_id, utilizador, resultado, observacao=""):
    version = (
        VersaoDocumento.objects.select_for_update()
        .select_related("documento__candidatura", "documento__requisito")
        .get(pk=versao_id)
    )
    candidature = version.documento.candidatura
    if not utilizador_pode_validar_documentos(utilizador, candidature):
        raise PermissionDenied("A validação documental exige um gestor autorizado.")
    if version.carregada_por_id == utilizador.pk:
        raise PermissionDenied("Não pode validar um documento que carregou.")
    allowed = {
        VersaoDocumento.EstadoValidacao.VALIDO: EstadoDocumento.VALIDO,
        VersaoDocumento.EstadoValidacao.INVALIDO: EstadoDocumento.INVALIDO,
    }
    if resultado not in allowed:
        raise ValidationError("Escolha uma decisão documental válida.")
    note = observacao.strip()
    if resultado == VersaoDocumento.EstadoValidacao.INVALIDO and not note:
        raise ValidationError("Explique por que motivo o documento é inválido.")
    if not version.corrente:
        raise ValidationError("Apenas a versão corrente pode ser validada.")
    now = timezone.now()
    VersaoDocumento.objects.filter(pk=version.pk).update(
        estado_validacao=resultado,
        validada_por=utilizador,
        validada_em=now,
        observacao_validacao=note,
    )
    state = allowed[resultado]
    Documento.objects.filter(pk=version.documento_id).update(
        estado_atual=state,
        atualizado_em=now,
    )
    if version.documento.requisito_id:
        RequisitoDocumento.objects.filter(pk=version.documento.requisito_id).update(
            estado=state,
            atualizado_em=now,
        )
    version.refresh_from_db()
    return version


@transaction.atomic
def dispensar_requisito(*, requisito_id, utilizador, motivo):
    requirement = (
        RequisitoDocumento.objects.select_for_update()
        .select_related("candidatura")
        .get(pk=requisito_id)
    )
    if not utilizador_pode_validar_documentos(utilizador, requirement.candidatura):
        raise PermissionDenied("A dispensa exige um gestor autorizado.")
    reason = motivo.strip()
    if not reason:
        raise ValidationError("A dispensa exige uma justificação.")
    now = timezone.now()
    RequisitoDocumento.objects.filter(pk=requirement.pk).update(
        estado=EstadoDocumento.DISPENSADO,
        dispensado_em=now,
        dispensado_por=utilizador,
        motivo_dispensa=reason,
        atualizado_em=now,
    )
    requirement.refresh_from_db()
    return requirement


@transaction.atomic
def criar_snapshot(
    *,
    candidatura_id,
    utilizador,
    finalidade,
    dados_adicionais=None,
    transicao=None,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    if candidature.estado_atual == Candidatura.Estado.RASCUNHO:
        _exigir_edicao(utilizador, candidature)
    elif not (
        candidature.estado_atual == Candidatura.Estado.PRONTA_SUBMISSAO
        and utilizador_pode_operar_candidatura(utilizador, candidature)
    ):
        raise PermissionDenied("Não pode criar uma fotografia nesta fase.")
    if finalidade not in SnapshotSubmissao.Finalidade.values:
        raise ValidationError("Escolha uma finalidade de snapshot válida.")
    if transicao and transicao.candidatura_id != candidature.pk:
        raise ValidationError("A transição não pertence à candidatura fotografada.")
    blocking = candidature.requisitos_documentais.filter(obrigatorio=True, bloqueante=True).exclude(
        estado__in=(EstadoDocumento.VALIDO, EstadoDocumento.DISPENSADO)
    )
    if blocking.exists():
        raise ValidationError("Resolva os requisitos documentais bloqueantes antes da fotografia.")
    versions = list(
        VersaoDocumento.objects.filter(
            documento__candidatura=candidature,
            corrente=True,
            estado_validacao=VersaoDocumento.EstadoValidacao.VALIDO,
        )
        .select_related("documento", "ficheiro")
        .order_by("documento__public_id", "numero")
    )
    sequence = (
        candidature.snapshots_submissao.filter(finalidade=finalidade).aggregate(
            highest=Max("sequencia")
        )["highest"]
        or 0
    ) + 1
    data = {
        "candidatura": str(candidature.public_id),
        "tipo": candidature.tipo,
        "versao_candidatura": candidature.versao,
        "conjunto_regras": candidature.conjunto_regras_id,
        "beneficiarios": list(
            candidature.beneficiarios.order_by("pk").values_list("pk", flat=True)
        ),
        "participacoes": list(
            candidature.beneficiarios.order_by("pk").values_list(
                "participacoes_formacao__pk", flat=True
            )
        ),
        "adicional": dados_adicionais or {},
    }
    hash_payload = {
        "dados": data,
        "documentos": [
            {
                "documento": str(version.documento.public_id),
                "numero": version.numero,
                "sha256": version.ficheiro.sha256,
            }
            for version in versions
        ],
        "versao_esquema": 1,
    }
    digest = hashlib.sha256(
        json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    snapshot = SnapshotSubmissao.objects.create(
        candidatura=candidature,
        transicao=transicao,
        finalidade=finalidade,
        sequencia=sequence,
        capturado_por=utilizador,
        dados=data,
        versao_esquema=1,
        hash_conteudo=digest,
    )
    snapshot.versoes_documentos.set(versions)
    return snapshot


def abrir_ficheiro_privado(version):
    stored = version.ficheiro
    if (
        stored.estado_upload != FicheiroArmazenado.EstadoUpload.CONCLUIDO
        or stored.estado_seguranca != FicheiroArmazenado.EstadoSeguranca.SEGURO
    ):
        raise ValidationError("O ficheiro não está disponível para descarga.")
    return default_storage.open(stored.chave_armazenamento, "rb")
