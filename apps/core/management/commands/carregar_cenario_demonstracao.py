import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.candidaturas.models import BeneficiarioCandidatura, Candidatura
from apps.candidaturas.services import (
    adicionar_beneficiario,
    associar_participacao,
    criar_candidatura_empresarial,
    criar_candidatura_individual,
    definir_conta_pagamento,
    executar_verificacoes_basicas,
)
from apps.contas.constants import GRUPO_ADMINISTRADOR, GRUPO_CANDIDATO, GRUPO_GESTOR
from apps.contas.models import PerfilCandidato, Utilizador
from apps.documentos.models import EstadoDocumento, FaseDocumento, VersaoDocumento
from apps.documentos.services import (
    carregar_documento_workflow,
    carregar_para_requisito,
    gerar_checklist_preparacao,
    validar_versao,
)
from apps.financeiro.models import ApoioFinanceiro, MovimentoFinanceiro
from apps.financeiro.services import (
    calcular_estimativas_candidatura,
    confirmar_valores_oficiais,
    registar_movimento,
)
from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import (
    AssociacaoEmpresa,
    ContaPagamento,
    Empresa,
    EntidadeFormadora,
    VinculoLaboral,
)
from apps.organizacoes.security import calcular_hash_iban
from apps.organizacoes.services import criar_conta_pagamento
from apps.regras.models import ConjuntoRegras, TipoDocumento
from apps.regras.services import publicar_conjunto
from apps.workflow.alerts import processar_alertas
from apps.workflow.models import PedidoEncerramento, Prazo, TermoAceitacao, TransicaoCandidatura
from apps.workflow.services import (
    aplicar_transicao,
    associar_termo_recebido,
    confirmar_regularizacao_financeira,
    confirmar_termo_aceite,
    guardar_resposta_rascunho,
    iniciar_preparacao_encerramento,
    registar_conclusao_encerramento,
    registar_decisao,
    registar_pedido_elementos,
    registar_resposta_completa,
    registar_resultado_participacao,
    submeter_encerramento,
)

DEMO_PASSWORD_ENV = "FORMAFLOW_DEMO_PASSWORD"
DEMO_COMPANY_NIPC = "123456789"
DEMO_PROVIDER_NIPC = "111111110"
DEMO_COMPANY_IBAN = "PT50000201231234567890154"
DEMO_CANDIDATE_IBAN = "PT50002700000001234567833"


class Command(BaseCommand):
    help = "Cria um cenário funcional, fictício e idempotente para a demonstração da PAP."

    def handle(self, *args, **options):
        password = os.getenv(DEMO_PASSWORD_ENV, "")
        if not password:
            raise CommandError(
                f"Defina {DEMO_PASSWORD_ENV} antes de criar as contas de demonstração."
            )
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError("A palavra-passe de demonstração não cumpre a política.") from error

        call_command("carregar_dados_demonstracao", stdout=self.stdout)
        result = self._create_scenario(password)
        alert_result = processar_alertas()
        self.stdout.write(
            self.style.SUCCESS(
                "Cenário fictício disponível: "
                f"{result['utilizadores']} contas, {result['candidaturas']} candidaturas e "
                f"{alert_result['notificacoes']} novos avisos."
            )
        )
        self.stdout.write(
            "Contas: admin.demo@example.test, gestor.demo@example.test, "
            "candidato.demo@example.test e beneficiario.demo@example.test. "
            "A palavra-passe não é apresentada."
        )

    def _user(self, *, email, first_name, last_name, password, superuser=False):
        user, _created = Utilizador.objects.get_or_create(
            email=email,
            defaults={
                "nome_proprio": first_name,
                "apelido": last_name,
                "is_active": True,
                "is_staff": superuser,
                "is_superuser": superuser,
                "equipa_interna": superuser,
            },
        )
        user.nome_proprio = first_name
        user.apelido = last_name
        user.is_active = True
        if superuser:
            user.is_staff = True
            user.is_superuser = True
            user.equipa_interna = True
        user.set_password(password)
        user.save()
        return user

    def _application(self, *, reference, creator, rules, company=None, link=None):
        application = Candidatura.objects.filter(referencia_externa=reference).first()
        if application:
            return application
        if company:
            application = criar_candidatura_empresarial(
                criada_por=creator,
                titular_empresa=company,
                conjunto_regras=rules,
            )
        else:
            application = criar_candidatura_individual(
                criada_por=creator,
                vinculo_referencia=link,
                conjunto_regras=rules,
            )
        application.referencia_externa = reference
        application.save(update_fields=("referencia_externa", "atualizado_em"))
        return application

    @staticmethod
    def _pdf(name):
        return SimpleUploadedFile(
            name,
            b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF",
            content_type="application/pdf",
        )

    def _training(self, *, reference, designation, provider):
        action, _created = AcaoFormacao.objects.get_or_create(
            referencia_externa=reference,
            defaults={
                "entidade_formadora": provider,
                "designacao": designation,
                "area_codigo": "481",
                "area_designacao": "Ciências informáticas",
                "modalidade": "Mista",
                "inicio_previsto": date(2026, 10, 1),
                "fim_previsto": date(2026, 11, 15),
                "local": "Viseu",
            },
        )
        ComponenteFormacao.objects.get_or_create(
            acao_formacao=action,
            ordem=1,
            defaults={
                "tipo": ComponenteFormacao.Tipo.CNQ,
                "codigo_cnq": f"UFCD-{reference[-3:]}",
                "designacao": "Desenvolvimento de aplicações web",
                "area_codigo": "481",
                "horas": Decimal("25"),
            },
        )
        return action

    @staticmethod
    def _payment_account(*, owner, iban, holder):
        owner_filter = {"empresa": owner} if isinstance(owner, Empresa) else {"candidato": owner}
        account = ContaPagamento.objects.filter(
            **owner_filter,
            iban_hash=calcular_hash_iban(iban),
        ).first()
        if account:
            return account
        return criar_conta_pagamento(
            iban=iban,
            nome_titular=holder,
            principal=True,
            **owner_filter,
        )

    def _validate_document(self, version, administrator):
        if version.estado_validacao != VersaoDocumento.EstadoValidacao.VALIDO:
            version = validar_versao(
                versao_id=version.pk,
                utilizador=administrator,
                resultado=VersaoDocumento.EstadoValidacao.VALIDO,
            )
        return version

    def _resolve_preparation_documents(self, application, actor, administrator):
        if application.estado_atual != Candidatura.Estado.RASCUNHO:
            return
        gerar_checklist_preparacao(candidatura_id=application.pk, utilizador=actor)
        for requirement in application.requisitos_documentais.filter(
            fase=FaseDocumento.PREPARACAO
        ).select_related("tipo_documento"):
            if requirement.estado == EstadoDocumento.VALIDO:
                continue
            version = (
                VersaoDocumento.objects.filter(
                    documento__requisito=requirement,
                    corrente=True,
                )
                .select_related("documento")
                .first()
            )
            if not version:
                version = carregar_para_requisito(
                    requisito_id=requirement.pk,
                    ficheiro=self._pdf(f"demo-{requirement.tipo_documento.codigo.lower()}.pdf"),
                    utilizador=actor,
                    titulo="Comprovativo fictício para demonstração",
                )
            self._validate_document(version, administrator)
        executar_verificacoes_basicas(candidatura_id=application.pk, utilizador=actor)

    def _workflow_document(
        self,
        *,
        application,
        actor,
        administrator,
        type_code,
        phase,
        filename,
    ):
        version = (
            VersaoDocumento.objects.filter(
                documento__candidatura=application,
                documento__tipo_documento__codigo=type_code,
                documento__fase=phase,
                corrente=True,
            )
            .select_related("documento")
            .first()
        )
        if not version:
            version = carregar_documento_workflow(
                candidatura_id=application.pk,
                tipo_documento=TipoDocumento.objects.get(codigo=type_code),
                ficheiro=self._pdf(filename),
                utilizador=actor,
                titulo="Evidência oficial fictícia para demonstração",
            )
        return self._validate_document(version, administrator)

    def _advance_to_analysis(self, application, actor, *, prefix, official_actor=None):
        official_actor = official_actor or actor
        base_time = application.criado_em + timedelta(minutes=1)
        if application.estado_atual == Candidatura.Estado.RASCUNHO:
            aplicar_transicao(
                candidatura_id=application.pk,
                codigo="TR-002",
                utilizador=actor,
                versao_esperada=application.versao,
                chave_idempotencia=f"{prefix}-preparar",
                efetiva_em=base_time,
                confirmacao=True,
                avisos_reconhecidos=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.PRONTA_SUBMISSAO:
            aplicar_transicao(
                candidatura_id=application.pk,
                codigo="TR-004",
                utilizador=actor,
                versao_esperada=application.versao,
                chave_idempotencia=f"{prefix}-submeter",
                efetiva_em=base_time + timedelta(hours=1),
                origem=TransicaoCandidatura.Origem.IEFPONLINE,
                referencia_externa=application.referencia_externa,
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.SUBMETIDA:
            aplicar_transicao(
                candidatura_id=application.pk,
                codigo="TR-006",
                utilizador=official_actor,
                versao_esperada=application.versao,
                chave_idempotencia=f"{prefix}-analise",
                efetiva_em=base_time + timedelta(hours=2),
                origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
                referencia_externa=f"{prefix.upper()}-ANALISE",
                confirmacao=True,
            )
            application.refresh_from_db()
        return base_time

    def _advance_business_case(self, application, manager, administrator):
        base_time = self._advance_to_analysis(application, manager, prefix="demo-emp")
        if (
            application.estado_atual == Candidatura.Estado.EM_ANALISE
            and not application.transicoes.filter(codigo="TR-007").exists()
        ):
            _transition, request = registar_pedido_elementos(
                candidatura_id=application.pk,
                questoes=[
                    {"texto": "Confirme os dados laborais dos beneficiários."},
                    {"texto": "Justifique o custo declarado da formação."},
                ],
                utilizador=manager,
                versao_esperada=application.versao,
                chave_idempotencia="demo-emp-pedido",
                recebido_em=base_time + timedelta(hours=3),
                referencia_externa="DEMO-EMP-PEDIDO-001",
                descricao="Pedido fictício para demonstrar a suspensão do prazo.",
                confirmacao=True,
            )
            application.refresh_from_db()
        else:
            request = application.pedidos_elementos.filter(
                referencia_externa="DEMO-EMP-PEDIDO-001"
            ).first()
        if application.estado_atual == Candidatura.Estado.AGUARDA_ELEMENTOS:
            for question in request.questoes.order_by("ordem"):
                if not question.respostas.exclude(estado="SUBSTITUIDA").exists():
                    guardar_resposta_rascunho(
                        questao_id=question.pk,
                        utilizador=manager,
                        texto="Informação fictícia confirmada para a demonstração.",
                    )
            registar_resposta_completa(
                pedido_id=request.pk,
                utilizador=manager,
                versao_esperada=application.versao,
                chave_idempotencia="demo-emp-resposta",
                efetiva_em=base_time + timedelta(hours=4),
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.EM_ANALISE:
            evidence = self._workflow_document(
                application=application,
                actor=manager,
                administrator=administrator,
                type_code="COMUNICACAO_IEFP",
                phase=FaseDocumento.ANALISE,
                filename="demo-decisao-empresarial.pdf",
            )
            beneficiaries = list(application.beneficiarios.order_by("pk"))
            results = {
                beneficiary.pk: (
                    BeneficiarioCandidatura.Resultado.DEFERIDA
                    if index == 0
                    else BeneficiarioCandidatura.Resultado.INDEFERIDA
                )
                for index, beneficiary in enumerate(beneficiaries)
            }
            reasons = {
                beneficiary.pk: "Limite fictício do cenário de demonstração."
                for beneficiary in beneficiaries[1:]
            }
            registar_decisao(
                candidatura_id=application.pk,
                resultados=results,
                motivos_beneficiarios=reasons,
                utilizador=manager,
                versao_esperada=application.versao,
                chave_idempotencia="demo-emp-decisao-parcial",
                efetiva_em=base_time + timedelta(hours=5),
                evidencia=evidence,
                referencia_externa="DEMO-EMP-DECISAO-001",
                confirmacao=True,
            )
            application.refresh_from_db()

    def _advance_individual_case(self, application, candidate_user, administrator):
        base_time = self._advance_to_analysis(
            application,
            candidate_user,
            prefix="demo-ind",
            official_actor=administrator,
        )
        evidence = None
        if application.estado_atual == Candidatura.Estado.EM_ANALISE:
            evidence = self._workflow_document(
                application=application,
                actor=candidate_user,
                administrator=administrator,
                type_code="COMUNICACAO_IEFP",
                phase=FaseDocumento.ANALISE,
                filename="demo-decisao-individual.pdf",
            )
            beneficiary = application.beneficiarios.get()
            registar_decisao(
                candidatura_id=application.pk,
                resultados={beneficiary.pk: BeneficiarioCandidatura.Resultado.DEFERIDA},
                utilizador=administrator,
                versao_esperada=application.versao,
                chave_idempotencia="demo-ind-decisao",
                efetiva_em=base_time + timedelta(hours=3),
                evidencia=evidence,
                referencia_externa="DEMO-IND-DECISAO-001",
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.APROVADA_AGUARDA_TERMO:
            term_version = self._workflow_document(
                application=application,
                actor=candidate_user,
                administrator=administrator,
                type_code="TERMO_ACEITACAO",
                phase=FaseDocumento.ACEITACAO,
                filename="demo-termo-individual.pdf",
            )
            term = application.termo_aceitacao
            if not term.documento_id:
                associar_termo_recebido(
                    candidatura_id=application.pk,
                    documento=term_version,
                    utilizador=candidate_user,
                    versao_esperada=application.versao,
                    recebido_em=base_time + timedelta(hours=4),
                    tipo_assinatura=TermoAceitacao.TipoAssinatura.DIGITAL_PESSOAL,
                )
            confirmar_termo_aceite(
                candidatura_id=application.pk,
                utilizador=administrator,
                versao_esperada=application.versao,
                chave_idempotencia="demo-ind-termo",
                efetiva_em=base_time + timedelta(hours=5),
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.APROVADA_ACOMPANHAMENTO:
            for participation in application.beneficiarios.get().participacoes_formacao.all():
                if not participation.resultado_registado_em:
                    registar_resultado_participacao(
                        participacao_id=participation.pk,
                        utilizador=candidate_user,
                        estado=AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO,
                        inicio_real=(base_time + timedelta(days=1)).date(),
                        fim_real=(base_time + timedelta(days=2)).date(),
                        horas_frequentadas=participation.horas_previstas,
                        dias_tres_ou_mais_horas=2,
                        custo_pago_formadora=participation.custo_declarado,
                    )
            iniciar_preparacao_encerramento(
                candidatura_id=application.pk,
                utilizador=administrator,
                versao_esperada=application.versao,
                chave_idempotencia="demo-ind-iniciar-encerramento",
                efetiva_em=base_time + timedelta(days=3),
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.ENCERRAMENTO_PREPARACAO:
            for requirement in application.requisitos_documentais.filter(
                fase=FaseDocumento.ENCERRAMENTO
            ).select_related("tipo_documento"):
                if requirement.estado == EstadoDocumento.VALIDO:
                    continue
                version = (
                    VersaoDocumento.objects.filter(
                        documento__requisito=requirement,
                        corrente=True,
                    )
                    .select_related("documento")
                    .first()
                )
                if not version:
                    version = carregar_para_requisito(
                        requisito_id=requirement.pk,
                        ficheiro=self._pdf(
                            f"demo-final-{requirement.tipo_documento.codigo.lower()}.pdf"
                        ),
                        utilizador=candidate_user,
                    )
                self._validate_document(version, administrator)
            evidence = evidence or self._workflow_document(
                application=application,
                actor=candidate_user,
                administrator=administrator,
                type_code="COMUNICACAO_IEFP",
                phase=FaseDocumento.ANALISE,
                filename="demo-decisao-individual.pdf",
            )
            submeter_encerramento(
                candidatura_id=application.pk,
                utilizador=administrator,
                versao_esperada=application.versao,
                chave_idempotencia="demo-ind-submeter-encerramento",
                efetiva_em=base_time + timedelta(days=4),
                referencia_externa="DEMO-IND-ENCERRAMENTO-001",
                evidencia=evidence,
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.ENCERRAMENTO_SUBMETIDO:
            aplicar_transicao(
                candidatura_id=application.pk,
                codigo="TR-017",
                utilizador=administrator,
                versao_esperada=application.versao,
                chave_idempotencia="demo-ind-analise-encerramento",
                efetiva_em=base_time + timedelta(days=5),
                origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
                referencia_externa="DEMO-IND-ANALISE-ENC-001",
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.ENCERRAMENTO_ANALISE:
            calcular_estimativas_candidatura(
                candidatura_id=application.pk,
                utilizador=administrator,
                usar_valores_finais=True,
            )
            for support in ApoioFinanceiro.objects.filter(
                beneficiario__candidatura=application,
                tipo=ApoioFinanceiro.Tipo.FORMACAO,
            ):
                if support.valor_final is None:
                    support = confirmar_valores_oficiais(
                        apoio_id=support.pk,
                        utilizador=administrator,
                        valor_aprovado=support.valor_estimado,
                        valor_final=support.valor_estimado,
                        confirmado_em=base_time + timedelta(days=5, hours=1),
                        referencia_externa="DEMO-IND-VALOR-OFICIAL-001",
                        evidencia=evidence,
                    )
                for planned in list(
                    support.movimentos.filter(estado=MovimentoFinanceiro.Estado.PREVISTO)
                ):
                    registar_movimento(
                        apoio_id=support.pk,
                        utilizador=administrator,
                        tipo=planned.tipo,
                        direcao=MovimentoFinanceiro.Direcao.CREDITO,
                        valor=planned.valor,
                        estado=MovimentoFinanceiro.Estado.CONFIRMADO,
                        efetivado_em=base_time + timedelta(days=5, hours=2),
                        referencia_externa=f"DEMO-PAG-{planned.tipo}",
                        chave_idempotencia=f"demo-ind-pag-{planned.tipo.lower()}",
                    )
            evidence = evidence or self._workflow_document(
                application=application,
                actor=candidate_user,
                administrator=administrator,
                type_code="COMUNICACAO_IEFP",
                phase=FaseDocumento.ANALISE,
                filename="demo-decisao-individual.pdf",
            )
            registar_conclusao_encerramento(
                candidatura_id=application.pk,
                utilizador=administrator,
                versao_esperada=application.versao,
                chave_idempotencia="demo-ind-conclusao",
                efetiva_em=base_time + timedelta(days=6),
                resultado_final=PedidoEncerramento.ResultadoFinal.CONCLUIDO,
                referencia_externa="DEMO-IND-CONCLUSAO-001",
                evidencia=evidence,
                confirmacao=True,
            )
            application.refresh_from_db()
        if application.estado_atual == Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO:
            evidence = evidence or self._workflow_document(
                application=application,
                actor=candidate_user,
                administrator=administrator,
                type_code="COMUNICACAO_IEFP",
                phase=FaseDocumento.ANALISE,
                filename="demo-decisao-individual.pdf",
            )
            confirmar_regularizacao_financeira(
                candidatura_id=application.pk,
                utilizador=administrator,
                versao_esperada=application.versao,
                chave_idempotencia="demo-ind-regularizacao",
                efetiva_em=base_time + timedelta(days=7),
                regularizacao_confirmada=True,
                referencia_externa="DEMO-IND-REGULARIZACAO-001",
                evidencia=evidence,
                confirmacao=True,
            )
            application.refresh_from_db()

    def _create_scenario(self, password):
        admin = self._user(
            email="admin.demo@example.test",
            first_name="Admin",
            last_name="Demonstração",
            password=password,
            superuser=True,
        )
        manager = self._user(
            email="gestor.demo@example.test",
            first_name="Gestor",
            last_name="Demonstração",
            password=password,
        )
        candidate_user = self._user(
            email="candidato.demo@example.test",
            first_name="Candidato",
            last_name="Demonstração",
            password=password,
        )
        beneficiary_user = self._user(
            email="beneficiario.demo@example.test",
            first_name="Beneficiário",
            last_name="Demonstração",
            password=password,
        )
        for user, group_name in (
            (admin, GRUPO_ADMINISTRADOR),
            (manager, GRUPO_GESTOR),
            (candidate_user, GRUPO_CANDIDATO),
            (beneficiary_user, GRUPO_CANDIDATO),
        ):
            group, _created = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

        candidate, _created = PerfilCandidato.objects.get_or_create(
            utilizador=candidate_user,
            defaults={"nif": "100000002", "data_nascimento": date(1994, 5, 20)},
        )
        second_candidate, _created = PerfilCandidato.objects.get_or_create(
            utilizador=beneficiary_user,
            defaults={"nif": "100000029", "data_nascimento": date(1991, 8, 12)},
        )
        company = Empresa.objects.get(nipc=DEMO_COMPANY_NIPC)
        provider = EntidadeFormadora.objects.get(nipc=DEMO_PROVIDER_NIPC)
        AssociacaoEmpresa.objects.get_or_create(
            utilizador=manager,
            empresa=company,
            papel=AssociacaoEmpresa.Papel.GESTOR,
            ativa=True,
            defaults={"inicio_em": timezone.now() - timedelta(days=30)},
        )
        link, _created = VinculoLaboral.objects.get_or_create(
            candidato=candidate,
            empresa=company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            defaults={
                "inicio_em": date(2026, 1, 1),
                "nivel_qualificacao": 4,
            },
        )
        VinculoLaboral.objects.get_or_create(
            candidato=second_candidate,
            empresa=company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            defaults={
                "inicio_em": date(2026, 1, 1),
                "nivel_qualificacao": 5,
            },
        )
        rules = ConjuntoRegras.objects.get(codigo="CHEQUE_FORMACAO", versao=1)
        if not rules.publicado_em:
            publicar_conjunto(rules.pk, admin)
            rules.refresh_from_db()

        business = self._application(
            reference="DEMO-EMP-001",
            creator=manager,
            company=company,
            rules=rules,
        )
        beneficiary = business.beneficiarios.filter(candidato=candidate).first()
        if not beneficiary:
            beneficiary = adicionar_beneficiario(
                candidatura_id=business.pk,
                candidato=candidate,
                utilizador=manager,
                versao_esperada=business.versao,
            )
            business.refresh_from_db()
        second_beneficiary = business.beneficiarios.filter(candidato=second_candidate).first()
        if not second_beneficiary and business.estado_atual == Candidatura.Estado.RASCUNHO:
            second_beneficiary = adicionar_beneficiario(
                candidatura_id=business.pk,
                candidato=second_candidate,
                utilizador=manager,
                versao_esperada=business.versao,
            )
            business.refresh_from_db()

        individual = self._application(
            reference="DEMO-IND-001",
            creator=candidate_user,
            link=link,
            rules=rules,
        )
        individual_beneficiary = individual.beneficiarios.get(candidato=candidate)

        business_training = self._training(
            reference="DEMO-FORM-EMP-001",
            designation="Aplicações web para empresa — demonstração",
            provider=provider,
        )
        individual_training = self._training(
            reference="DEMO-FORM-IND-001",
            designation="Aplicações web individual — demonstração",
            provider=provider,
        )
        for application, application_beneficiary, action, actor in (
            (business, beneficiary, business_training, manager),
            (business, second_beneficiary, business_training, manager),
            (individual, individual_beneficiary, individual_training, candidate_user),
        ):
            if (
                application.estado_atual == Candidatura.Estado.RASCUNHO
                and application_beneficiary
                and not application_beneficiary.participacoes_formacao.filter(
                    acao_formacao=action
                ).exists()
            ):
                application.refresh_from_db()
                associar_participacao(
                    candidatura_id=application.pk,
                    beneficiario=application_beneficiary,
                    acao_formacao=action,
                    horas_previstas=Decimal("25"),
                    custo_declarado=Decimal("175"),
                    utilizador=actor,
                    versao_esperada=application.versao,
                )

        company_account = self._payment_account(
            owner=company,
            iban=DEMO_COMPANY_IBAN,
            holder="Empresa Demonstração, Lda.",
        )
        candidate_account = self._payment_account(
            owner=candidate,
            iban=DEMO_CANDIDATE_IBAN,
            holder="Candidato Demonstração",
        )
        business.refresh_from_db()
        if business.estado_atual == Candidatura.Estado.RASCUNHO and not business.conta_pagamento_id:
            definir_conta_pagamento(
                candidatura_id=business.pk,
                conta_pagamento=company_account,
                utilizador=manager,
                versao_esperada=business.versao,
            )
        individual.refresh_from_db()
        if (
            individual.estado_atual == Candidatura.Estado.RASCUNHO
            and not individual.conta_pagamento_id
        ):
            definir_conta_pagamento(
                candidatura_id=individual.pk,
                conta_pagamento=candidate_account,
                utilizador=candidate_user,
                versao_esperada=individual.versao,
            )

        business.refresh_from_db()
        individual.refresh_from_db()
        self._resolve_preparation_documents(business, manager, admin)
        self._resolve_preparation_documents(individual, candidate_user, admin)
        business.refresh_from_db()
        individual.refresh_from_db()
        self._advance_business_case(business, manager, admin)
        self._advance_individual_case(individual, candidate_user, admin)

        Prazo.objects.get_or_create(
            candidatura=business,
            codigo_regra="DEMO-PRAZO-URGENTE",
            defaults={
                "tipo": Prazo.Tipo.OUTRO,
                "conjunto_regras": rules,
                "inicio_em": timezone.now() - timedelta(days=3),
                "unidade": Prazo.Unidade.DIAS_CONSECUTIVOS,
                "duracao": 4,
                "limite_calculado": timezone.now() + timedelta(days=1),
            },
        )
        return {"utilizadores": 4, "candidaturas": 2}
