from django.core.management.base import BaseCommand, CommandError

from apps.core.scheduling import Outcome, get_jobs, run_job


class Command(BaseCommand):
    help = "Exécute les tâches périodiques dues (à appeler par le cron toutes les 5 minutes)."

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", help="Lister les tâches déclarées.")
        parser.add_argument("--job", help="N'exécuter que la tâche portant ce nom.")
        parser.add_argument(
            "--force", action="store_true", help="Exécuter même si la tâche n'est pas due."
        )

    def handle(self, *args, **options):
        jobs = get_jobs()

        if options["list"]:
            for job in jobs:
                self.stdout.write(f"{job.name}  (toutes les {job.every})")
            return

        if options["job"]:
            jobs = [job for job in jobs if job.name == options["job"]]
            if not jobs:
                raise CommandError(f"Tâche inconnue : {options['job']}")

        failed = []
        for job in jobs:
            outcome = run_job(job, force=options["force"])
            self.stdout.write(f"{job.name} : {outcome}")
            if outcome is Outcome.FAILED:
                failed.append(job.name)

        if failed:
            raise CommandError(f"Tâche(s) en échec : {', '.join(failed)}")
