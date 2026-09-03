from django.core.management.base import BaseCommand

from apps.workflow.alerts import processar_alertas


class Command(BaseCommand):
    help = "Cria tarefas e notificações idempotentes para prazos próximos ou vencidos."

    def handle(self, *args, **options):
        result = processar_alertas()
        self.stdout.write(
            self.style.SUCCESS(
                "Alertas processados: "
                f"{result['prazos']} prazo(s), "
                f"{result['notificacoes']} notificação(ões) nova(s), "
                f"{result['tarefas']} tarefa(s) nova(s)."
            )
        )
