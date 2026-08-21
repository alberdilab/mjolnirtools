import contextlib
import os
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


CHECKLIST_XML_WITH_CONSTRAINTS = """<?xml version="1.0" encoding="UTF-8"?>
<CHECKLIST_SET>
  <CHECKLIST accession="ERC000025" checklistType="Sample">
    <DESCRIPTOR>
      <LABEL>Constrained checklist</LABEL>
      <FIELD_GROUP>
        <FIELD>
          <LABEL>relationship to oxygen</LABEL>
          <NAME>relationship_to_oxygen</NAME>
          <FIELD_TYPE>
            <TEXT_CHOICE_FIELD>
              <TEXT_VALUE><VALUE>aerobe</VALUE></TEXT_VALUE>
              <TEXT_VALUE><VALUE>anaerobe</VALUE></TEXT_VALUE>
              <TEXT_VALUE><VALUE>facultative</VALUE></TEXT_VALUE>
            </TEXT_CHOICE_FIELD>
          </FIELD_TYPE>
          <MANDATORY>optional</MANDATORY>
        </FIELD>
        <FIELD>
          <LABEL>number of replicons</LABEL>
          <NAME>number_of_replicons</NAME>
          <FIELD_TYPE>
            <TEXT_FIELD>
              <REGEX_VALUE>[+-]?[0-9]+</REGEX_VALUE>
            </TEXT_FIELD>
          </FIELD_TYPE>
          <MANDATORY>optional</MANDATORY>
        </FIELD>
      </FIELD_GROUP>
    </DESCRIPTOR>
  </CHECKLIST>
</CHECKLIST_SET>
"""


def _constrained_tsv(path, oxygen_value, replicons_value):
    path.write_text(
        "#checklist_accession\tERC000025\n"
        "sample_alias\tsample_title\ttaxon_id\tscientific_name\trelationship_to_oxygen\tnumber_of_replicons\n"
        "#units\t\t\t\t\t\n"
        f"sample9\tTitle\t9606\tHomo sapiens\t{oxygen_value}\t{replicons_value}\n"
    )


class EnaTests(unittest.TestCase):
    def test_parse_checklist_xml_extracts_fields(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML)

        self.assertEqual(checklist.accession, "ERC999999")
        self.assertEqual(checklist.label, "Test checklist")
        self.assertEqual(checklist.fields[0].name, "project_name")
        self.assertTrue(checklist.fields[0].mandatory)
        self.assertEqual(checklist.fields[1].units, ("C",))

    def test_parse_checklist_xml_extracts_choices_and_regex(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML_WITH_CONSTRAINTS)
        by_name = {field.name: field for field in checklist.fields}

        self.assertEqual(
            by_name["relationship_to_oxygen"].choices,
            ("aerobe", "anaerobe", "facultative"),
        )
        self.assertEqual(by_name["number_of_replicons"].regex, "[+-]?[0-9]+")

    def test_validation_flags_controlled_vocabulary_and_regex_violations(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML_WITH_CONSTRAINTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            _constrained_tsv(path, "BADVALUE", "notanumber")
            errors, _, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertTrue(
            any("relationship_to_oxygen" in e and "'BADVALUE'" in e for e in errors),
            errors,
        )
        self.assertTrue(
            any("number_of_replicons" in e and "[+-]?[0-9]+" in e for e in errors),
            errors,
        )

    def test_validation_accepts_valid_controlled_vocabulary_and_regex(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML_WITH_CONSTRAINTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            _constrained_tsv(path, "aerobe", "3")
            errors, _, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertEqual(errors, [])

    def test_autofix_normalises_controlled_vocabulary_case(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML_WITH_CONSTRAINTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            _constrained_tsv(path, "Aerobe", "3")
            fixes = ena.autofix_metadata_tsv(path, checklist)
            errors, samples, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertEqual(len(fixes), 1)
        self.assertIn("'Aerobe' -> 'aerobe'", fixes[0])
        self.assertEqual(errors, [])
        self.assertEqual(samples[0]["relationship_to_oxygen"], "aerobe")

    def test_autofix_leaves_unmatchable_values_untouched(self):
        checklist = ena.parse_checklist_xml(CHECKLIST_XML_WITH_CONSTRAINTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            _constrained_tsv(path, "BADVALUE", "3")
            fixes = ena.autofix_metadata_tsv(path, checklist)
            samples = ena.validate_metadata_tsv(path, checklist)[1]

        self.assertEqual(fixes, [])
        self.assertEqual(samples[0]["relationship_to_oxygen"], "BADVALUE")

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

        self.assertIn("Column 'project_name' is mandatory for ERC999999 but missing/empty in 1 row(s).", errors)

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
        # ENA keys attributes on the checklist field LABEL, not the underscored NAME.
        self.assertIn("<TAG>project name</TAG>", xml_text)
        self.assertNotIn("<TAG>project_name</TAG>", xml_text)

    def test_write_sample_xml_uses_parenthesised_labels_and_checklist_units(self):
        checklist_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<CHECKLIST_SET>\n'
            '  <CHECKLIST accession="ERC000013" checklistType="Sample">\n'
            '    <DESCRIPTOR>\n'
            '      <LABEL>Test</LABEL>\n'
            '      <FIELD_GROUP>\n'
            '        <FIELD>\n'
            '          <LABEL>geographic location (country and/or sea)</LABEL>\n'
            '          <NAME>geographic_location_country_andor_sea</NAME>\n'
            '          <MANDATORY>mandatory</MANDATORY>\n'
            '        </FIELD>\n'
            '        <FIELD>\n'
            '          <LABEL>sample storage temperature</LABEL>\n'
            '          <NAME>sample_storage_temperature</NAME>\n'
            '          <UNITS><UNIT>°C</UNIT></UNITS>\n'
            '          <MANDATORY>optional</MANDATORY>\n'
            '        </FIELD>\n'
            '      </FIELD_GROUP>\n'
            '    </DESCRIPTOR>\n'
            '  </CHECKLIST>\n'
            '</CHECKLIST_SET>\n'
        )
        checklist = ena.parse_checklist_xml(checklist_xml)
        samples = [{
            "sample_alias": "s1",
            "sample_title": "Marine microbiome",
            "taxon_id": "408172",
            "scientific_name": "marine metagenome",
            "geographic_location_country_andor_sea": "Denmark: Kattegat",
            "sample_storage_temperature": "-80",
        }]
        headers = [
            "sample_alias", "sample_title", "taxon_id", "scientific_name",
            "geographic_location_country_andor_sea", "sample_storage_temperature",
        ]
        # A deliberately corrupted #units row must not reach the XML: the unit is
        # taken from the checklist definition instead.
        units = ["#units", "", "", "", "", "BÂ°C"]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.xml"
            ena.write_sample_xml(samples, headers, units, checklist, path)
            xml_text = path.read_text(encoding="utf-8")

        self.assertIn("<TAG>geographic location (country and/or sea)</TAG>", xml_text)
        self.assertIn("<VALUE>Denmark: Kattegat</VALUE>", xml_text)
        self.assertIn("<TAG>sample storage temperature</TAG>", xml_text)
        self.assertIn("<UNITS>°C</UNITS>", xml_text)
        self.assertNotIn("BÂ°C", xml_text)

    def test_validation_rejects_non_iso_collection_date(self):
        checklist = ena.fallback_checklist("ERC000013")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            path.write_text(
                "#checklist_accession\tERC000013\n"
                "sample_alias\tsample_title\ttaxon_id\tscientific_name\tcollection_date\n"
                "#units\t\t\t\t\n"
                "#field_type\tmandatory\tmandatory\tmandatory\toptional\tmandatory\n"
                "sample1\tMy sample\t408172\tmarine metagenome\t3/6/24\n"
                "sample2\tMy sample\t408172\tmarine metagenome\t2024-06-03\n"
            )
            errors, _, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertTrue(
            any("collection_date" in e and "3/6/24" in e for e in errors),
            f"expected a collection_date error mentioning 3/6/24, got: {errors}",
        )

    def test_collection_date_accepts_iso_ranges_and_missing_terms(self):
        for value in ["2024", "2024-06", "2024-06-03", "2024-06-03/2024-06-05",
                      "not applicable", "missing: control sample"]:
            self.assertTrue(ena._is_valid_collection_date(value), value)
        for value in ["3/6/24", "06-03-2024", "June 2024", "2024/06/03/extra"]:
            self.assertFalse(ena._is_valid_collection_date(value), value)

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
                manifests=[base / "reads_sample1.manifest.txt"],
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

    def test_write_submission_script_loops_over_multiple_manifests(self):
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
                manifests=[base / "reads_s1.manifest.txt", base / "reads_s2.manifest.txt"],
                input_dir=base / "reads",
                output_dir=base / "out",
                test_service=False,
                source=base / "reads",
                keep_original=True,
            )
            text = script.read_text()

        self.assertIn("reads_s1.manifest.txt", text)
        self.assertIn("reads_s2.manifest.txt", text)
        self.assertIn("for MANIFEST_FILE in", text)
        self.assertIn("-manifest \"$MANIFEST_FILE\"", text)

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

            console = Console(file=StringIO(), width=200)
            ena._report_file_detection(console, files, max_show=3)
            output = console.file.getvalue()

            self.assertIn("10 data file(s)", output)
            self.assertIn("+7 more", output)

    def test_valid_instruments_covers_all_platforms(self):
        for platform in ena.VALID_PLATFORMS:
            self.assertIn(platform, ena.VALID_INSTRUMENTS, f"VALID_INSTRUMENTS missing entry for {platform}")
            self.assertGreater(len(ena.VALID_INSTRUMENTS[platform]), 0)

    def test_prompt_from_list_returns_selected_option(self):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=80)

        with mock.patch("mjolnirtools.ena.typer.prompt", return_value="3"):
            result = ena._prompt_from_list(console, "Test field", ("alpha", "beta", "gamma"), "Test")

        self.assertEqual(result, "gamma")

    def test_prompt_from_list_rejects_out_of_range_then_accepts(self):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=80)

        with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["0", "99", "1"]):
            result = ena._prompt_from_list(console, "Test", ("only",), "Test")

        self.assertEqual(result, "only")

    def test_write_manifest_template_reads_with_library_fills_all_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "reads"
            source.mkdir()
            read = source / "sample1_R1.fastq.gz"
            read.write_text("data")
            manifest = Path(tmpdir) / "reads_sample1.manifest.txt"
            library = ena.ReadsLibraryMetadata(
                platform="ILLUMINA",
                instrument="Illumina NovaSeq X",
                library_name="lib-sample1",
                library_source="METAGENOMIC",
                library_selection="RANDOM",
                library_strategy="WGS",
            )

            ena.write_manifest_template(
                "reads",
                source,
                [read],
                "PRJEB1",
                "sample1",
                manifest,
                library=library,
            )
            text = manifest.read_text()
            has_todos = ena.manifest_has_todos(manifest)

        self.assertIn("STUDY\tPRJEB1", text)
        self.assertIn("SAMPLE\tsample1", text)
        self.assertIn("NAME\tsample1", text)
        self.assertIn("PLATFORM\tILLUMINA", text)
        self.assertIn("INSTRUMENT\tIllumina NovaSeq X", text)
        self.assertIn("LIBRARY_NAME\tlib-sample1", text)
        self.assertIn("LIBRARY_SOURCE\tMETAGENOMIC", text)
        self.assertIn("LIBRARY_SELECTION\tRANDOM", text)
        self.assertIn("LIBRARY_STRATEGY\tWGS", text)
        self.assertFalse(has_todos)

    def test_validation_catches_empty_mandatory_field_from_field_type_row(self):
        """#field_type row drives mandatory enforcement even when checklist has no fields."""
        checklist = ena.fallback_checklist("ERC000022")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            path.write_text(
                "#checklist_accession\tERC000022\n"
                "sample_alias\tsample_title\ttaxon_id\tscientific_name\tcollection date\tbroad-scale environmental context\n"
                "#units\t\t\t\t\t\n"
                "#field_type\tmandatory\tmandatory\tmandatory\toptional\tmandatory\tmandatory\n"
                "sample_1\tMy sample\t408169\tmetagenome\t\t\n"
            )
            errors, _, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertIn("Column 'collection date' is mandatory for ERC000022 but missing/empty in 1 row(s).", errors)
        self.assertIn("Column 'broad-scale environmental context' is mandatory for ERC000022 but missing/empty in 1 row(s).", errors)

    def test_validation_passes_when_all_field_type_mandatory_fields_are_filled(self):
        """Validation succeeds when the #field_type row marks fields mandatory and they are filled."""
        checklist = ena.fallback_checklist("ERC000022")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "samples.tsv"
            path.write_text(
                "#checklist_accession\tERC000022\n"
                "sample_alias\tsample_title\ttaxon_id\tscientific_name\tcollection date\n"
                "#units\t\t\t\t\n"
                "#field_type\tmandatory\tmandatory\tmandatory\toptional\tmandatory\n"
                "sample_1\tMy sample\t408169\tmetagenome\t2024-01-15\n"
            )
            errors, samples, _, _ = ena.validate_metadata_tsv(path, checklist)

        self.assertEqual(errors, [])
        self.assertEqual(samples[0]["collection date"], "2024-01-15")

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


class SampleGroupingReviewTests(unittest.TestCase):
    """The wizard must show the detected grouping and let the user correct it."""

    def _console(self) -> tuple[Console, StringIO]:
        buffer = StringIO()
        return Console(file=buffer, width=140, force_terminal=False), buffer

    @contextlib.contextmanager
    def _dataset(self, names):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            files = []
            for name in names:
                path = root / name
                path.touch()
                files.append(path)
            yield root, files

    NOVOGENE = [
        f"{alias}_EKDL240003470-1A_{flowcell}_{lane}_{mate}.fq.gz"
        for alias in ("AC79", "AC80")
        for flowcell, lane in (("223JWCLT4", "L2"), ("22JVFTLT3", "L1"))
        for mate in ("1", "2")
    ]

    def test_accepting_keeps_the_detected_grouping(self):
        console, buffer = self._console()
        with self._dataset(self.NOVOGENE) as (root, files):
            with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["accept"]):
                grouping = ena._review_sample_grouping(console, files, root, root / "sample_files.tsv")

        self.assertIsNotNone(grouping)
        self.assertEqual(grouping.aliases, ["AC79", "AC80"])
        self.assertEqual(len(grouping.runs), 4)
        output = buffer.getvalue()
        self.assertIn("8 data file(s)", output)
        self.assertIn("4 run(s) in 2 sample(s)", output)
        self.assertIn("AC79", output)

    def test_aborting_returns_none(self):
        console, _ = self._console()
        with self._dataset(self.NOVOGENE) as (root, files):
            with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["abort"]):
                grouping = ena._review_sample_grouping(console, files, root, root / "sample_files.tsv")

        self.assertIsNone(grouping)

    def test_choosing_another_scheme_regroups_the_files(self):
        console, _ = self._console()
        with self._dataset(self.NOVOGENE) as (root, files):
            options = ena.samples_module.scheme_options(ena.samples_module.detect_runs(files)[0])
            choice = str(1 + [option.scheme for option in options].index("stem"))
            with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["scheme", choice, "accept"]):
                grouping = ena._review_sample_grouping(console, files, root, root / "sample_files.tsv")

        self.assertEqual(len(grouping.samples), 4)
        self.assertEqual(len(grouping.files), 8)

    def test_custom_pattern_overrides_the_alias(self):
        console, _ = self._console()
        with self._dataset(self.NOVOGENE) as (root, files):
            with mock.patch(
                "mjolnirtools.ena.typer.prompt",
                side_effect=["pattern", r"^(?P<sample>AC\d+)_EKDL(?P<batch>\d+)", "accept"],
            ):
                grouping = ena._review_sample_grouping(console, files, root, root / "sample_files.tsv")

        self.assertEqual(grouping.aliases, ["AC79", "AC80"])

    def test_editing_the_mapping_file_replaces_the_grouping(self):
        console, _ = self._console()
        with self._dataset(["a_R1.fq.gz", "a_R2.fq.gz"]) as (root, files):
            mapping = root / "sample_files.tsv"

            def _edit(_message):
                mapping.write_text(
                    "#sample_files\tv1\n"
                    "sample_alias\trun_name\tread\tfile\n"
                    "Renamed\trun-42\t1\ta_R1.fq.gz\n"
                    "Renamed\trun-42\t2\ta_R2.fq.gz\n"
                )

            with mock.patch("mjolnirtools.ena.click.pause", side_effect=_edit):
                with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["edit", "accept"]):
                    grouping = ena._review_sample_grouping(console, files, root, mapping)

        self.assertEqual(grouping.aliases, ["Renamed"])
        self.assertEqual(grouping.runs[0].run_name, "run-42")

    def test_a_broken_edit_keeps_the_previous_grouping(self):
        console, buffer = self._console()
        with self._dataset(["a_R1.fq.gz", "a_R2.fq.gz"]) as (root, files):
            mapping = root / "sample_files.tsv"

            def _edit(_message):
                mapping.write_text("this is not a mapping file\n")

            with mock.patch("mjolnirtools.ena.click.pause", side_effect=_edit):
                with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["edit", "accept"]):
                    grouping = ena._review_sample_grouping(console, files, root, mapping)

        self.assertEqual(grouping.aliases, ["a"])
        self.assertIn("Keeping the previous grouping", buffer.getvalue())
        self.assertNotIn("Traceback", buffer.getvalue())

    def test_grouping_warnings_are_shown(self):
        console, buffer = self._console()
        with self._dataset(["a_R1.fq.gz", "a_R2.fq.gz", "b_R1.fq.gz"]) as (root, files):
            with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["accept"]):
                ena._review_sample_grouping(console, files, root, root / "sample_files.tsv")

        self.assertIn("Warning:", buffer.getvalue())
        self.assertIn("no mate", buffer.getvalue())

    def test_discover_data_files_ignores_non_sequence_files(self):
        with self._dataset(["notes.txt", "checksums.md5"]) as (root, _files):
            self.assertEqual(ena.discover_data_files(root, "reads"), [])

    def test_manifest_uses_the_run_name_and_the_sample_alias(self):
        with self._dataset(["AC79_L1_1.fq.gz", "AC79_L1_2.fq.gz"]) as (root, files):
            manifest = root / "reads_AC79_L1.manifest.txt"
            ena.write_manifest_template(
                "reads", root, files, "PRJEB1", "AC79", manifest, run_name="AC79_L1"
            )
            text = manifest.read_text()

        self.assertIn("SAMPLE\tAC79", text)
        self.assertIn("NAME\tAC79_L1", text)
        self.assertEqual(text.count("FASTQ\t"), 2)

    def test_reads_manifest_rejects_more_than_one_read_pair(self):
        with self._dataset(["a_1.fq.gz", "a_2.fq.gz", "b_1.fq.gz", "b_2.fq.gz"]) as (root, files):
            with self.assertRaises(ena.errors_module.UserError) as caught:
                ena.write_manifest_template(
                    "reads", root, files, "PRJEB1", "a", root / "m.txt", run_name="a"
                )

        self.assertIn("4 read files", caught.exception.message)

    def test_full_multi_lane_dataset_yields_one_row_per_sample_and_one_manifest_per_run(self):
        """Regression for the 460-file dataset that produced 377 bogus samples."""
        names = [
            f"AC{index}_EKDL240003470-1A_{flowcell}_{lane}_{mate}.fq.gz"
            for index in range(79, 79 + 115)
            for flowcell, lane in (("223JWCLT4", "L2"), ("22JVFTLT3", "L1"))
            for mate in ("1", "2")
        ]
        console, _ = self._console()
        with self._dataset(names) as (root, _created):
            data_files = ena.discover_data_files(root, "reads")
            self.assertEqual(len(data_files), 460)

            with mock.patch("mjolnirtools.ena.typer.prompt", side_effect=["accept"]):
                grouping = ena._review_sample_grouping(console, data_files, root, root / "sample_files.tsv")

            self.assertEqual(len(grouping.samples), 115)
            self.assertEqual(len(grouping.runs), 230)
            self.assertEqual(len(grouping.files), 460)

            workspace = root / "workspace"
            ena.samples_module.write_sample_mapping_tsv(workspace / "sample_files.tsv", grouping, root)
            metadata = workspace / "samples.tsv"
            checklist = ena.parse_checklist_xml(CHECKLIST_XML)
            ena.write_metadata_template(checklist, metadata, sample_names=grouping.aliases)
            data_rows = [
                line
                for line in metadata.read_text().splitlines()
                if line.strip() and not line.startswith(("#", "sample_alias"))
            ]
            self.assertEqual(len(data_rows), 115)

            matched, unclaimed = ena.samples_module.reconcile_aliases(grouping, grouping.aliases)
            self.assertEqual(unclaimed, [])

            fastq_counts = []
            for alias, runs in matched.items():
                for run in runs:
                    manifest = workspace / f"reads_{run.run_name}.manifest.txt"
                    ena.write_manifest_template(
                        "reads", root, list(run.files), "PRJEB1", alias, manifest, run_name=run.run_name
                    )
                    text = manifest.read_text()
                    self.assertIn(f"SAMPLE\t{alias}", text)
                    self.assertIn(f"NAME\t{run.run_name}", text)
                    fastq_counts.append(text.count("FASTQ\t"))

            self.assertEqual(len(fastq_counts), 230)
            self.assertEqual(set(fastq_counts), {2})
            self.assertEqual(len(list(workspace.glob("reads_*.manifest.txt"))), 230)


class TransferWizardErrorHandlingTests(unittest.TestCase):
    def _console(self) -> tuple[Console, StringIO]:
        buffer = StringIO()
        return Console(file=buffer, width=100, force_terminal=False), buffer

    def test_workspace_prompt_accepts_a_writable_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            console, _ = self._console()
            default = Path(tmpdir) / "mt-ena-run"
            with mock.patch("mjolnirtools.ena.typer.prompt", return_value=str(default)):
                workspace = ena._prompt_workspace_directory(console, default)

            self.assertEqual(workspace, default.resolve())
            self.assertTrue(default.is_dir())

    def test_workspace_prompt_reprompts_after_permission_error(self):
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions")
        with tempfile.TemporaryDirectory() as tmpdir:
            locked = Path(tmpdir) / "locked"
            locked.mkdir(mode=0o500)
            writable = Path(tmpdir) / "workspace"
            console, buffer = self._console()
            try:
                with mock.patch(
                    "mjolnirtools.ena.typer.prompt",
                    side_effect=[str(locked / "run"), str(writable)],
                ):
                    workspace = ena._prompt_workspace_directory(console, locked / "run")
            finally:
                locked.chmod(0o700)

            self.assertEqual(workspace, writable.resolve())
            output = buffer.getvalue()
            self.assertIn("Permission denied", output)
            self.assertNotIn("Traceback", output)

    def test_workspace_prompt_gives_up_after_repeated_failures(self):
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions")
        with tempfile.TemporaryDirectory() as tmpdir:
            locked = Path(tmpdir) / "locked"
            locked.mkdir(mode=0o500)
            console, buffer = self._console()
            try:
                with mock.patch(
                    "mjolnirtools.ena.typer.prompt", return_value=str(locked / "run")
                ):
                    workspace = ena._prompt_workspace_directory(console, locked / "run")
            finally:
                locked.chmod(0o700)

            self.assertIsNone(workspace)
            self.assertIn("Could not set up a workspace directory", buffer.getvalue())

    def _sample_metadata_args(self, base: Path) -> dict:
        submission_xml = base / "submission.xml"
        sample_xml = base / "sample.xml"
        submission_xml.write_text("<SUBMISSION />")
        sample_xml.write_text("<SAMPLE_SET />")
        return {
            "credentials": config_module.EnaCredentials("Webin-1", "secret", base / "credentials"),
            "submission_xml": submission_xml,
            "sample_xml": sample_xml,
            "receipt_xml": base / "receipt.xml",
            "test_service": True,
            "service_label": "test service",
        }

    def test_sample_metadata_submission_retries_after_a_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            console, buffer = self._console()
            with mock.patch(
                "mjolnirtools.ena.submit_sample_registration",
                side_effect=[TimeoutError("timed out"), True],
            ) as submit:
                with mock.patch("mjolnirtools.ena.typer.confirm", return_value=True):
                    submitted = ena._submit_sample_metadata_interactive(
                        console=console, **self._sample_metadata_args(Path(tmpdir))
                    )

            self.assertTrue(submitted)
            self.assertEqual(submit.call_count, 2)
            output = buffer.getvalue()
            self.assertIn("timed out", output)
            self.assertIn("Sample metadata submitted", output)

    def test_sample_metadata_submission_stops_when_retry_is_declined(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            console, buffer = self._console()
            with mock.patch(
                "mjolnirtools.ena.submit_sample_registration",
                side_effect=TimeoutError("timed out"),
            ) as submit:
                with mock.patch("mjolnirtools.ena.typer.confirm", return_value=False):
                    submitted = ena._submit_sample_metadata_interactive(
                        console=console, **self._sample_metadata_args(Path(tmpdir))
                    )

            self.assertFalse(submitted)
            self.assertEqual(submit.call_count, 1)
            self.assertIn("cancelled", buffer.getvalue().lower())

    def test_sample_metadata_submission_does_not_retry_a_rejected_receipt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            console, buffer = self._console()
            with mock.patch(
                "mjolnirtools.ena.submit_sample_registration", return_value=False
            ) as submit:
                with mock.patch("mjolnirtools.ena.typer.confirm", return_value=True) as confirm:
                    submitted = ena._submit_sample_metadata_interactive(
                        console=console, **self._sample_metadata_args(Path(tmpdir))
                    )

            self.assertFalse(submitted)
            self.assertEqual(submit.call_count, 1)
            confirm.assert_not_called()
            self.assertIn("Receipt", buffer.getvalue())

    def test_wizard_converts_filesystem_errors_into_messages(self):
        buffer = StringIO()
        error = PermissionError(13, "Permission denied", "/maps/projects/demo/run")
        with mock.patch("mjolnirtools.ena._run_transfer_wizard", side_effect=error):
            with contextlib.redirect_stdout(buffer):
                exit_code = ena.run_transfer_wizard(None, True)

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("Permission denied", output)
        self.assertIn("/maps/projects/demo/run", output)
        self.assertNotIn("Traceback", output)

    def test_wizard_reports_cancellation(self):
        buffer = StringIO()
        with mock.patch("mjolnirtools.ena._run_transfer_wizard", side_effect=KeyboardInterrupt):
            with contextlib.redirect_stdout(buffer):
                exit_code = ena.run_transfer_wizard(None, True)

        self.assertEqual(exit_code, 130)
        self.assertIn("cancelled", buffer.getvalue().lower())

    def test_wizard_rejects_unreadable_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing"
            console, buffer = self._console()

            exit_code = ena._run_transfer_wizard(console, str(missing), True)

            self.assertEqual(exit_code, 1)
            self.assertIn("Path not found", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
