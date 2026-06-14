import tempfile
import unittest
import urllib.error
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

from rich.console import Console

from mjolnirtools import config as config_module
from mjolnirtools import ena


CHECKLIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CHECKLIST_SET>
  <CHECKLIST accession="ERC999999" checklistType="Sample">
    <DESCRIPTOR>
      <LABEL>Test checklist</LABEL>
      <FIELD_GROUP>
        <FIELD>
          <LABEL>project name</LABEL>
          <NAME>project_name</NAME>
          <DESCRIPTION>Project name</DESCRIPTION>
          <MANDATORY>mandatory</MANDATORY>
          <MULTIPLICITY>single</MULTIPLICITY>
        </FIELD>
        <FIELD>
          <LABEL>temperature</LABEL>
          <NAME>temperature</NAME>
          <UNITS><UNIT>C</UNIT></UNITS>
          <MANDATORY>optional</MANDATORY>
          <MULTIPLICITY>single</MULTIPLICITY>
        </FIELD>
      </FIELD_GROUP>
    </DESCRIPTOR>
  </CHECKLIST>
</CHECKLIST_SET>
"""


class EnaTests(unittest.TestCase):
    def test_parse_checklist_xml_extracts_fields(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML)

        self.assertEqual(checklist.accession, "ERC999999")
        self.assertEqual(checklist.label, "Test checklist")
        self.assertEqual(checklist.fields[0].name, "project_name")
        self.assertTrue(checklist.fields[0].mandatory)
        self.assertEqual(checklist.fields[1].units, ("C",))

    def test_metadata_template_and_validation(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            ena.write_metadata_template(checklist, path)
            text = path.read_text()
            self.assertIn("#checklist_accession\tERC999999", text)
            self.assertIn("sample_alias\tsample_title\ttaxon_id\tscientific_name\tproject_name", text)
            self.assertNotIn("\ttemperature", text)

            path.write_text(
                "#checklist_accession\tERC999999\n"
                "sample_alias\tsample_title\ttaxon_id\tscientific_name\tproject_name\n"
                "#units\t\t\t\t\n"
                "sample_1\tSample title\t9606\tHomo sapiens\tTest project\n"
            )
            errors, samples, headers, units = ena.validate_metadata_tsv(path, checklist)

        self.assertEqual(errors, [])
        self.assertEqual(samples[0]["sample_alias"], "sample_1")
        self.assertIn("project_name", headers)
        self.assertEqual(units[0], "#units")

    def test_metadata_validation_reports_missing_mandatory_field(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            path.write_text(
                "#checklist_accession\tERC999999\n"
                "sample_alias\tsample_title\ttaxon_id\tscientific_name\tproject_name\n"
                "#units\t\t\t\t\n"
                "sample_1\tSample title\t9606\tHomo sapiens\t\n"
            )
            errors, _, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertIn("Row 4: project_name is mandatory for ERC999999.", errors)

    def test_write_sample_xml_adds_checklist_and_attributes(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML)
        samples = [{
            "sample_alias": "sample_1",
            "sample_title": "Sample title",
            "taxon_id": "9606",
            "scientific_name": "Homo sapiens",
            "project_name": "Test project",
        }]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.xml"
            ena.write_sample_xml(
                samples,
                ["sample_alias", "sample_title", "taxon_id", "scientific_name", "project_name"],
                ["#units", "", "", "", ""],
                checklist,
                path,
            )
            xml_text = path.read_text()

        self.assertIn("<SAMPLE alias=\"sample_1\">", xml_text)
        self.assertIn("<TAG>ENA-CHECKLIST</TAG>", xml_text)
        self.assertIn("<VALUE>ERC999999</VALUE>", xml_text)
        self.assertIn("<TAG>project_name</TAG>", xml_text)

    def test_write_project_xml_and_submission_hold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            project_xml = base / "project.xml"
            submission_xml = base / "submission.xml"
            title = "Study title with enough detail"
            description = "Study description with enough detail"

            ena.write_project_xml(
                "study_alias",
                title,
                description,
                project_xml,
            )
            ena.write_submission_xml(submission_xml, hold_until="2026-12-31")

            project_text = project_xml.read_text()
            submission_text = submission_xml.read_text()

        self.assertIn('<PROJECT alias="study_alias">', project_text)
        self.assertIn(f"<TITLE>{title}</TITLE>", project_text)
        self.assertIn(f"<DESCRIPTION>{description}</DESCRIPTION>", project_text)
        self.assertIn("<SEQUENCING_PROJECT />", project_text)
        self.assertIn("<ADD />", submission_text)
        self.assertIn('<HOLD HoldUntilDate="2026-12-31" />', submission_text)

    def test_write_project_xml_rejects_short_title_and_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_xml = Path(tmpdir) / "project.xml"

            with self.assertRaisesRegex(ValueError, "Study title must be at least 20"):
                ena.write_project_xml("study_alias", "sdf", "sdf", project_xml)

            self.assertFalse(project_xml.exists())

    def test_parse_project_accession_from_receipt(self):
        accession = ena.parse_project_accession_from_receipt(
            '<RECEIPT success="true"><PROJECT accession="PRJEB12345" /></RECEIPT>'
        )

        self.assertEqual(accession, "PRJEB12345")

    def test_parse_project_accession_reports_receipt_failure(self):
        with self.assertRaisesRegex(ValueError, "bad alias"):
            ena.parse_project_accession_from_receipt(
                '<RECEIPT success="false"><MESSAGES><ERROR>bad alias</ERROR></MESSAGES></RECEIPT>'
            )

    def test_submit_project_registration_posts_project_xml(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'<RECEIPT success="true"><PROJECT accession="PRJEB12345" /></RECEIPT>'

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            project_xml = base / "project.xml"
            submission_xml = base / "submission.xml"
            receipt_xml = base / "receipt.xml"
            project_xml.write_text("<PROJECT_SET />")
            submission_xml.write_text("<SUBMISSION />")
            credentials = config_module.EnaCredentials("Webin-1", "secret", base / "credentials")

            with mock.patch("mjolnirtools.ena.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
                accession = ena.submit_project_registration(
                    credentials=credentials,
                    submission_xml=submission_xml,
                    project_xml=project_xml,
                    receipt_xml=receipt_xml,
                    test_service=True,
                )

            request = urlopen.call_args.args[0]
            body = request.data
            receipt_text = receipt_xml.read_text()

        self.assertEqual(accession, "PRJEB12345")
        self.assertIn("wwwdev.ebi.ac.uk", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Basic V2ViaW4tMTpzZWNyZXQ=")
        self.assertIn(b'name="SUBMISSION"; filename="submission.xml"', body)
        self.assertIn(b'name="PROJECT"; filename="project.xml"', body)
        self.assertIn("PRJEB12345", receipt_text)

    def test_submit_project_registration_saves_ena_error_receipt(self):
        receipt = b'<RECEIPT success="false"><MESSAGES><ERROR>bad project</ERROR></MESSAGES></RECEIPT>'
        http_error = urllib.error.HTTPError(
            "https://wwwdev.ebi.ac.uk/ena/submit/drop-box/submit/",
            400,
            "Bad Request",
            {},
            BytesIO(receipt),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            project_xml = base / "project.xml"
            submission_xml = base / "submission.xml"
            receipt_xml = base / "receipt.xml"
            project_xml.write_text("<PROJECT_SET />")
            submission_xml.write_text("<SUBMISSION />")
            credentials = config_module.EnaCredentials("Webin-1", "secret", base / "credentials")

            with mock.patch("mjolnirtools.ena.urllib.request.urlopen", side_effect=http_error):
                with self.assertRaisesRegex(ValueError, "bad project"):
                    ena.submit_project_registration(
                        credentials=credentials,
                        submission_xml=submission_xml,
                        project_xml=project_xml,
                        receipt_xml=receipt_xml,
                        test_service=True,
                    )

            receipt_text = receipt_xml.read_text()

        self.assertIn("bad project", receipt_text)

    def test_write_manifest_template_for_reads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "reads"
            source.mkdir()
            read = source / "sample_R1.fastq.gz"
            read.write_text("data")
            manifest = Path(tmpdir) / "reads.manifest.txt"

            ena.write_manifest_template(
                "reads",
                source,
                [read],
                "PRJEB1",
                "sample_1",
                manifest,
            )
            text = manifest.read_text()
            has_todos = ena.manifest_has_todos(manifest)

        self.assertIn("STUDY\tPRJEB1", text)
        self.assertIn("SAMPLE\tsample_1", text)
        self.assertIn("FASTQ\tsample_R1.fastq.gz", text)
        self.assertTrue(has_todos)

    def test_write_manifest_for_study_reuses_completed_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            test_manifest = base / "reads.manifest.txt"
            production_manifest = base / "reads.production.manifest.txt"
            test_manifest.write_text(
                "STUDY\tTEST_PRJ\n"
                "SAMPLE\tsample_1\n"
                "NAME\trun42\n"
                "PLATFORM\tILLUMINA\n"
            )

            ena.write_manifest_for_study(test_manifest, production_manifest, "PRJEB12345")
            text = production_manifest.read_text()

        self.assertIn("STUDY\tPRJEB12345", text)
        self.assertIn("SAMPLE\tsample_1", text)
        self.assertIn("PLATFORM\tILLUMINA", text)
        self.assertNotIn("TEST_PRJ", text)

    def test_write_submission_script_uses_screen_ready_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            script = base / "submit.sh"
            ena.write_submission_script(
                script_path=script,
                credentials_path=base / "credentials",
                sample_xml=base / "sample.xml",
                submission_xml=base / "submission.xml",
                receipt_xml=base / "receipt.xml",
                log_path=base / "submit.log",
                webin_cli_jar=base / "webin-cli.jar",
                context="reads",
                manifest=base / "reads.manifest.txt",
                input_dir=base / "reads",
                output_dir=base / "out",
                test_service=True,
                source=base / "reads",
                keep_original=True,
            )
            text = script.read_text()

        self.assertIn("curl -sS", text)
        self.assertIn("wwwdev.ebi.ac.uk", text)
        self.assertIn("java -jar", text)
        self.assertIn("tee -a \"$LOG_FILE\"", text)
        self.assertIn("-context reads", text)
        self.assertIn("-submit -test", text)
        self.assertIn("Source kept.", text)

    def test_write_test_then_production_script_runs_test_before_production(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            script = base / "submit-ena.sh"
            test_script = base / "submit-ena-test.sh"
            production_script = base / "submit-ena-production.sh"
            ena.write_test_then_production_script(
                script_path=script,
                test_script_path=test_script,
                production_script_path=production_script,
                log_path=base / "submit-ena.log",
            )
            text = script.read_text()

        self.assertIn("set -euo pipefail", text)
        self.assertLess(text.index(str(test_script)), text.index(str(production_script)))
        self.assertIn("Running ENA production submission", text)

    def test_ena_credentials_support_multiple_users(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with mock.patch.multiple(
                config_module,
                _ENA_CONFIG_DIR=base,
                _ENA_CREDENTIALS_FILE=base / "credentials",
                _ENA_CREDENTIALS_DIR=base / "credentials.d",
            ):
                config_module._write_ena_credentials("Webin-111", "secret-1")
                config_module._write_ena_credentials("Webin-222", "secret-2")

                credentials = config_module._list_ena_credentials()
                default_username, default_password = config_module._read_ena_credentials()

        self.assertEqual(default_username, "Webin-222")
        self.assertEqual(default_password, "secret-2")
        self.assertEqual([credential.username for credential in credentials], ["Webin-222", "Webin-111"])
        self.assertEqual(credentials[0].password, "secret-2")
        self.assertEqual(credentials[1].password, "secret-1")

    def test_ena_credentials_migrate_legacy_default_when_adding_second_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            credentials_file = base / "credentials"
            credentials_file.write_text("username=Webin-111\npassword=secret-1\n")
            with mock.patch.multiple(
                config_module,
                _ENA_CONFIG_DIR=base,
                _ENA_CREDENTIALS_FILE=credentials_file,
                _ENA_CREDENTIALS_DIR=base / "credentials.d",
            ):
                config_module._write_ena_credentials("Webin-222", "secret-2")

                credentials = config_module._list_ena_credentials()

        self.assertEqual([credential.username for credential in credentials], ["Webin-222", "Webin-111"])
        self.assertEqual(credentials[0].password, "secret-2")
        self.assertEqual(credentials[1].password, "secret-1")

    def test_select_webin_credentials_prompts_when_multiple_users_are_configured(self):
        credentials = [
            config_module.EnaCredentials("Webin-111", "secret-1", Path("/tmp/one")),
            config_module.EnaCredentials("Webin-222", "secret-2", Path("/tmp/two")),
        ]
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=120)

        with mock.patch("mjolnirtools.ena.config_module._list_ena_credentials", return_value=credentials):
            with mock.patch("mjolnirtools.ena.typer.prompt", return_value="2") as prompt:
                selected = ena._select_webin_credentials(console)

        self.assertEqual(selected, credentials[1])
        prompt.assert_called_once_with("  Webin user", default="1")
        self.assertIn("Select the ENA Webin account", output.getvalue())

    def test_select_or_register_study_can_create_new_study(self):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=120)

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            credentials = config_module.EnaCredentials("Webin-1", "secret", workspace / "credentials")
            with mock.patch("mjolnirtools.ena.typer.confirm", side_effect=[False, True]) as confirm:
                with mock.patch(
                    "mjolnirtools.ena.typer.prompt",
                    side_effect=[
                        "study_alias",
                        "Study title with enough detail",
                        "Study description with enough detail",
                    ],
                ):
                    with mock.patch("mjolnirtools.ena.click.prompt", return_value=""):
                        with mock.patch("mjolnirtools.ena.submit_project_registration", return_value="PRJEB12345") as submit:
                            study = ena._select_or_register_study(
                                console=console,
                                workspace=workspace,
                                credentials=credentials,
                                test_service=True,
                            )

            project_text = (workspace / "test-project.xml").read_text()

        self.assertEqual(study, "PRJEB12345")
        confirm.assert_any_call("  Do you already have an ENA study/BioProject?", default=False)
        self.assertIn('<PROJECT alias="study_alias">', project_text)
        submit.assert_called_once()
        text = output.getvalue()
        self.assertIn("Study registered", text)
        self.assertIn("The study alias is your private Webin identifier", text)
        self.assertIn("The study title is the human-readable name", text)
        self.assertIn("at least 20 characters", text)
        self.assertIn("The study description explains the purpose and scope", text)
        self.assertIn("unique for your Webin account", text)
        self.assertIn("date cannot be in the past", text)

    def test_prompt_help_prints_title_and_message(self):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=120)

        ena._print_prompt_help(console, "Study accession or alias", "Register the study before this step.")
        text = output.getvalue()

        self.assertIn("Study accession or alias", text)
        self.assertIn("Register the study before this step.", text)
        self.assertIn("press Enter to use it", text)

    def test_prompt_help_can_render_nested_indentation(self):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=120)

        ena._print_prompt_help(console, "New study alias", "Use a short alias.", indent=4)
        text = output.getvalue()

        self.assertIn("\n    ╭─ New study alias", text)
        self.assertIn("\n    │ Use a short alias.", text)

    def test_submission_context_help_lists_choices_and_docs(self):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=180)

        ena._print_submission_context_help(console)
        text = output.getvalue()

        self.assertIn("ENA Webin-CLI uses the -context option", text)
        self.assertIn("reads", text)
        self.assertIn("genome", text)
        self.assertIn("transcriptome", text)
        self.assertIn("sequence", text)
        self.assertIn("Webin-CLI submission guide", text)
        self.assertNotIn("https://ena-docs.readthedocs.io", text)

    def test_submission_runner_uses_current_screen_when_inside_screen(self):
        command = ena.build_submission_runner_command(
            Path("/work/submit-ena.sh"),
            "mt-transfer-ena-20260612-090000",
            inside_screen=True,
        )

        self.assertEqual(command, ["bash", "/work/submit-ena.sh"])

    def test_submission_runner_opens_screen_when_not_inside_screen(self):
        command = ena.build_submission_runner_command(
            Path("/work/submit-ena.sh"),
            "mt-transfer-ena-20260612-090000",
            inside_screen=False,
        )

        self.assertEqual(
            command,
            [
                "screen",
                "-dmS",
                "mt-transfer-ena-20260612-090000",
                "bash",
                "/work/submit-ena.sh",
            ],
        )

    def test_auto_discover_source_finds_files_in_root_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir).resolve()
            (base / "sample.fastq.gz").touch()

            discovered = ena.auto_discover_source(base)

            self.assertEqual(discovered, base)

    def test_auto_discover_source_finds_files_in_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir).resolve()
            subdir = base / "sample_1"
            subdir.mkdir()
            (subdir / "reads.fq").touch()

            discovered = ena.auto_discover_source(base)

            self.assertEqual(discovered, subdir)

    def test_auto_discover_source_returns_root_when_files_exist_there(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir).resolve()
            (base / "assembly.fasta.gz").touch()
            subdir = base / "sample_1"
            subdir.mkdir()
            (subdir / "reads.fastq").touch()

            discovered = ena.auto_discover_source(base)

            self.assertEqual(discovered, base)

    def test_auto_discover_source_returns_none_when_no_files_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir).resolve()
            (base / "other_file.txt").touch()
            subdir = base / "subdir"
            subdir.mkdir()
            (subdir / "data.txt").touch()

            discovered = ena.auto_discover_source(base)

            self.assertIsNone(discovered)

    def test_auto_discover_source_uses_current_directory_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir).resolve()
            (base / "data.fasta").touch()

            # Can't easily test this without changing cwd, so we pass the path explicitly
            discovered = ena.auto_discover_source(base)
            self.assertEqual(discovered, base)

    def test_guess_pairing_detects_paired_r1_r2_notation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [
                base / "sample_R1.fastq",
                base / "sample_R2.fastq",
            ]
            for f in files:
                f.touch()

            pairing = ena._guess_pairing(files)
            self.assertEqual(pairing, "paired")

    def test_guess_pairing_detects_paired_underscore_notation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [
                base / "sample_1.fq.gz",
                base / "sample_2.fq.gz",
            ]
            for f in files:
                f.touch()

            pairing = ena._guess_pairing(files)
            self.assertEqual(pairing, "paired")

    def test_guess_pairing_detects_single_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [base / "sample.fastq"]
            files[0].touch()

            pairing = ena._guess_pairing(files)
            self.assertEqual(pairing, "single")

    def test_guess_pairing_empty_list_returns_single(self):
        pairing = ena._guess_pairing([])
        self.assertEqual(pairing, "single")

    def test_report_file_detection_shows_count_and_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [
                base / "sample_R1.fastq",
                base / "sample_R2.fastq",
                base / "sample_R1_trimmed.fastq",
            ]
            for f in files:
                f.touch()

            console = Console(file=StringIO(), width=100)
            ena._report_file_detection(console, files)
            output = console.file.getvalue()

            self.assertIn("3 data file(s)", output)
            self.assertIn("paired", output)
            self.assertIn("sample_R1.fastq", output)
            self.assertIn("sample_R2.fastq", output)

    def test_report_file_detection_truncates_long_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [base / f"file_{i}.fastq" for i in range(10)]
            for f in files:
                f.touch()

            console = Console(file=StringIO(), width=100)
            ena._report_file_detection(console, files, max_show=3)
            output = console.file.getvalue()

            self.assertIn("10 data file(s)", output)
            self.assertIn("+7 more", output)

    def test_extract_sample_names_removes_extensions_and_paired_indicators(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [
                base / "sample1_R1.fastq.gz",
                base / "sample1_R2.fastq.gz",
                base / "sample2_1.fq.gz",
                base / "sample2_2.fq.gz",
                base / "sample3.fasta",
            ]
            for f in files:
                f.touch()

            samples = ena.extract_sample_names(files)

            self.assertEqual(samples, ["sample1", "sample2", "sample3"])

    def test_extract_sample_names_handles_various_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [
                base / "reads.fastq.gz",
                base / "genome.fasta",
                base / "transcript.fa.gz",
                base / "sequence.embl",
            ]
            for f in files:
                f.touch()

            samples = ena.extract_sample_names(files)

            self.assertEqual(samples, ["genome", "reads", "sequence", "transcript"])

    def test_extract_sample_names_deduplicates_paired_reads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            files = [
                base / "mysample_forward.fastq.gz",
                base / "mysample_reverse.fastq.gz",
            ]
            for f in files:
                f.touch()

            samples = ena.extract_sample_names(files)

            self.assertEqual(samples, ["mysample"])

    def test_metadata_validation_groups_non_ascii_errors_by_column(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            path.write_text(
                "#checklist_accession\tERC999999\n"
                "sample_alias\tsample_title\ttaxon_id\tscientific_name\tproject_name\n"
                "#units\t\t\t\t\n"
                "sample_1\tSample with µg DNA\t9606\tHomo sapiens\tTest project\n"
                "sample_2\tSample 2\t9606\tHomo sapiens\tTest project\n"
                "sample_3\tAnother µg sample\t9606\tHomo sapiens\tTest project\n",
                encoding="utf-8",
            )
            errors, _, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertEqual(len(errors), 1)
        self.assertIn("Column 'sample_title'", errors[0])
        self.assertIn("2 row(s)", errors[0])
        self.assertIn("U+00B5", errors[0])

    def test_write_metadata_template_with_sample_names(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            ena.write_metadata_template(
                checklist,
                path,
                sample_names=["sample_1", "sample_2", "sample_3"],
            )
            text = path.read_text()

            self.assertIn("#checklist_accession\tERC999999", text)
            self.assertIn("sample_1\tTODO\tTODO", text)
            self.assertIn("sample_2\tTODO\tTODO", text)
            self.assertIn("sample_3\tTODO\tTODO", text)

            # Verify each sample appears on its own line
            lines = [line for line in text.split("\n") if line.strip()]
            self.assertEqual(len(lines), 7)  # accession, headers, units, field_type, and 3 samples


if __name__ == "__main__":
    unittest.main()
