"""Database dump and restore management commands.

Provides commands for:
- Creating database dumps (full and data-only)
- Restoring from dumps
- Managing dump files
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Manage database dumps for backup and development"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action", help="Action to perform")

        # Dump action
        dump_parser = subparsers.add_parser("dump", help="Create a database dump")
        dump_parser.add_argument(
            "--name",
            type=str,
            help="Custom name for the dump file",
        )
        dump_parser.add_argument(
            "--data-only",
            action="store_true",
            help="Only dump data, not schema",
        )
        dump_parser.add_argument(
            "--schema-only",
            action="store_true",
            help="Only dump schema, not data",
        )
        dump_parser.add_argument(
            "--output-dir",
            type=str,
            default="docker/postgres/dumps",
            help="Output directory for dump files",
        )
        dump_parser.add_argument(
            "--compress",
            action="store_true",
            help="Compress the dump with gzip",
        )

        # Restore action
        restore_parser = subparsers.add_parser("restore", help="Restore from a dump")
        restore_parser.add_argument(
            "file",
            type=str,
            help="Path to the dump file to restore",
        )
        restore_parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean (drop) existing objects before restoring",
        )

        # List action
        list_parser = subparsers.add_parser("list", help="List available dump files")
        list_parser.add_argument(
            "--dir",
            type=str,
            default="docker/postgres/dumps",
            help="Directory to list dumps from",
        )

        # Clean action
        clean_parser = subparsers.add_parser("clean", help="Clean old dump files")
        clean_parser.add_argument(
            "--keep",
            type=int,
            default=5,
            help="Number of recent dumps to keep",
        )
        clean_parser.add_argument(
            "--dir",
            type=str,
            default="docker/postgres/dumps",
            help="Directory to clean",
        )

    def handle(self, *args, **options):
        action = options.get("action")

        if not action:
            self.stdout.write(
                self.style.ERROR("Please specify an action: dump, restore, list, clean")
            )
            return

        if action == "dump":
            self.handle_dump(options)
        elif action == "restore":
            self.handle_restore(options)
        elif action == "list":
            self.handle_list(options)
        elif action == "clean":
            self.handle_clean(options)

    def get_db_config(self):
        """Get database configuration from Django settings."""
        db_config = settings.DATABASES.get("default", {})
        return {
            "name": db_config.get("NAME", "boilerplate_db"),
            "user": db_config.get("USER", "postgres"),
            "password": db_config.get("PASSWORD", "postgres"),
            "host": db_config.get("HOST", "localhost"),
            "port": db_config.get("PORT", "5432"),
        }

    def handle_dump(self, options):
        """Create a database dump."""
        db_config = self.get_db_config()
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if options.get("name"):
            filename = f"{options['name']}_{timestamp}.sql"
        else:
            suffix = ""
            if options.get("data_only"):
                suffix = "_data"
            elif options.get("schema_only"):
                suffix = "_schema"
            filename = f"dump{suffix}_{timestamp}.sql"

        if options.get("compress"):
            filename += ".gz"

        output_path = output_dir / filename

        # Build pg_dump command
        cmd = [
            "pg_dump",
            f"--host={db_config['host']}",
            f"--port={db_config['port']}",
            f"--username={db_config['user']}",
            "--format=plain",
            "--no-owner",
            "--no-privileges",
        ]

        if options.get("data_only"):
            cmd.append("--data-only")
        elif options.get("schema_only"):
            cmd.append("--schema-only")

        cmd.append(db_config["name"])

        # Set password in environment
        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["password"]

        self.stdout.write(f"Creating dump: {output_path}")

        try:
            if options.get("compress"):
                # Pipe through gzip
                with open(output_path, "wb") as f:
                    dump_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                    )
                    gzip_process = subprocess.Popen(
                        ["gzip"],
                        stdin=dump_process.stdout,
                        stdout=f,
                        stderr=subprocess.PIPE,
                    )
                    dump_process.stdout.close()
                    _, gzip_err = gzip_process.communicate()
                    _, dump_err = dump_process.communicate()

                    if dump_process.returncode != 0:
                        raise CommandError(f"pg_dump failed: {dump_err.decode()}")
                    if gzip_process.returncode != 0:
                        raise CommandError(f"gzip failed: {gzip_err.decode()}")
            else:
                with open(output_path, "w") as f:
                    result = subprocess.run(
                        cmd,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        env=env,
                        check=True,
                    )

            # Get file size
            size = output_path.stat().st_size
            size_str = self.format_size(size)

            self.stdout.write(
                self.style.SUCCESS(f"✅ Dump created: {output_path} ({size_str})")
            )

        except subprocess.CalledProcessError as e:
            raise CommandError(f"Dump failed: {e.stderr.decode()}")
        except FileNotFoundError:
            raise CommandError("pg_dump not found. Is PostgreSQL client installed?")

    def handle_restore(self, options):
        """Restore from a database dump."""
        db_config = self.get_db_config()
        file_path = Path(options["file"])

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        self.stdout.write(f"Restoring from: {file_path}")

        # Build psql command
        cmd = [
            "psql",
            f"--host={db_config['host']}",
            f"--port={db_config['port']}",
            f"--username={db_config['user']}",
            "--dbname=" + db_config["name"],
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["password"]

        try:
            if str(file_path).endswith(".gz"):
                # Decompress and pipe to psql
                gunzip_process = subprocess.Popen(
                    ["gunzip", "-c", str(file_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                psql_process = subprocess.Popen(
                    cmd,
                    stdin=gunzip_process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                )
                gunzip_process.stdout.close()
                stdout, stderr = psql_process.communicate()

                if psql_process.returncode != 0:
                    self.stdout.write(
                        self.style.WARNING(f"Warnings: {stderr.decode()}")
                    )
            else:
                with open(file_path) as f:
                    result = subprocess.run(
                        cmd,
                        check=False,
                        stdin=f,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                    )
                    if result.stderr:
                        self.stdout.write(
                            self.style.WARNING(f"Warnings: {result.stderr.decode()}")
                        )

            self.stdout.write(self.style.SUCCESS("✅ Database restored successfully"))

        except FileNotFoundError as e:
            raise CommandError(f"Required command not found: {e}")
        except Exception as e:
            raise CommandError(f"Restore failed: {e}")

    def handle_list(self, options):
        """List available dump files."""
        dump_dir = Path(options["dir"])

        if not dump_dir.exists():
            self.stdout.write(f"No dumps directory found: {dump_dir}")
            return

        dumps = sorted(
            dump_dir.glob("*.sql*"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        if not dumps:
            self.stdout.write("No dump files found")
            return

        self.stdout.write(self.style.SUCCESS("\n📁 Available Database Dumps:"))
        self.stdout.write("-" * 60)

        for dump in dumps:
            stat = dump.stat()
            size = self.format_size(stat.st_size)
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            self.stdout.write(f"  {dump.name:<40} {size:>10}  {mtime}")

        self.stdout.write("-" * 60)
        self.stdout.write(f"Total: {len(dumps)} dump(s)\n")

    def handle_clean(self, options):
        """Clean old dump files, keeping the most recent ones."""
        dump_dir = Path(options["dir"])
        keep = options["keep"]

        if not dump_dir.exists():
            self.stdout.write("No dumps directory found")
            return

        dumps = sorted(
            dump_dir.glob("*.sql*"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        if len(dumps) <= keep:
            self.stdout.write(f"Found {len(dumps)} dumps, keeping all (limit: {keep})")
            return

        to_delete = dumps[keep:]

        self.stdout.write(f"Keeping {keep} most recent dumps")
        self.stdout.write(f"Deleting {len(to_delete)} old dumps:")

        for dump in to_delete:
            self.stdout.write(f"  • Deleting: {dump.name}")
            dump.unlink()

        self.stdout.write(
            self.style.SUCCESS(f"✅ Cleaned up {len(to_delete)} old dumps")
        )

    def format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
