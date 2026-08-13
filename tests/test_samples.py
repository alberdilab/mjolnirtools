import tempfile
import unittest
from pathlib import Path

from mjolnirtools import samples
from mjolnirtools.errors import UserError


def _paths(names, base="/data"):
    return [Path(base) / name for name in names]


def _novogene_names(aliases=("AC79", "AC80", "AC81")):
    """File names in the layout that first exposed the detection bug."""
    return [
        f"{alias}_EKDL240003470-1A_{flowcell}_{lane}_{mate}.fq.gz"
        for alias in aliases
        for flowcell, lane in (("223JWCLT4", "L2"), ("22JVFTLT3", "L1"))
        for mate in ("1", "2")
    ]


class StripExtensionTests(unittest.TestCase):
    def test_longest_matching_extension_wins(self):
        self.assertEqual(samples.strip_sequence_extension("reads.fq.gz"), "reads")
        self.assertEqual(samples.strip_sequence_extension("reads.fastq.gz"), "reads")
        self.assertEqual(samples.strip_sequence_extension("assembly.fasta"), "assembly")
        self.assertEqual(samples.strip_sequence_extension("aln.bam"), "aln")

    def test_unknown_extension_is_left_alone(self):
        self.assertEqual(samples.strip_sequence_extension("notes.txt"), "notes.txt")


class RunDetectionTests(unittest.TestCase):
    def test_mate_marker_is_only_matched_at_the_end_of_the_name(self):
        # '_2' also occurs inside the flowcell field '223JWCLT4'; matching it
        # there is what previously split mates into separate samples.
        runs, warnings = samples.detect_runs(_paths(_novogene_names(("AC79",))))

        self.assertEqual(warnings, [])
        self.assertEqual(
            [run.run_name for run in runs],
            [
                "AC79_EKDL240003470-1A_223JWCLT4_L2",
                "AC79_EKDL240003470-1A_22JVFTLT3_L1",
            ],
        )
        self.assertTrue(all(run.pairing == "paired" for run in runs))
        self.assertTrue(all(run.file_count == 2 for run in runs))

    def test_forward_file_is_first_in_a_pair(self):
        runs, _ = samples.detect_runs(_paths(["s_R2.fastq.gz", "s_R1.fastq.gz"]))

        self.assertEqual([f.name for f in runs[0].files], ["s_R1.fastq.gz", "s_R2.fastq.gz"])

    def test_bcl2fastq_chunk_suffix_is_stripped(self):
        runs, _ = samples.detect_runs(
            _paths(["Sample_S1_L001_R1_001.fastq.gz", "Sample_S1_L001_R2_001.fastq.gz"])
        )

        self.assertEqual([run.run_name for run in runs], ["Sample_S1_L001"])
        self.assertEqual(runs[0].pairing, "paired")

    def test_marker_variants_are_recognised(self):
        for first, second in (
            ("s_R1.fastq.gz", "s_R2.fastq.gz"),
            ("s_read1.fastq.gz", "s_read2.fastq.gz"),
            ("s_forward.fastq.gz", "s_reverse.fastq.gz"),
            ("s.1.fastq.gz", "s.2.fastq.gz"),
            ("s-1.fastq.gz", "s-2.fastq.gz"),
            ("s_fwd.fastq.gz", "s_rev.fastq.gz"),
            ("s_f.fastq.gz", "s_r.fastq.gz"),
        ):
            with self.subTest(first=first):
                runs, _ = samples.detect_runs(_paths([first, second]))
                self.assertEqual(len(runs), 1, first)
                self.assertEqual(runs[0].pairing, "paired")
                self.assertEqual(runs[0].run_name, "s")

    def test_mixed_marker_conventions_are_both_detected(self):
        runs, _ = samples.detect_runs(
            _paths(["a_R1.fq.gz", "a_R2.fq.gz", "b_1.fq.gz", "b_2.fq.gz"])
        )

        self.assertEqual([(run.run_name, run.pairing) for run in runs], [("a", "paired"), ("b", "paired")])

    def test_ambiguous_markers_need_a_complete_pair(self):
        # '_1' here is a lane, not a read mate: there is no '_2' counterpart.
        runs, warnings = samples.detect_runs(_paths(["sample_L1.fq.gz"]))

        self.assertEqual([run.run_name for run in runs], ["sample_L1"])
        self.assertEqual(runs[0].pairing, "single")
        self.assertEqual(warnings, [])

    def test_unpaired_r1_is_reported_and_kept_as_single_end(self):
        runs, warnings = samples.detect_runs(_paths(["a_R1.fq.gz", "a_R2.fq.gz", "b_R1.fq.gz"]))

        self.assertEqual([(run.run_name, run.pairing) for run in runs], [("a", "paired"), ("b", "single")])
        self.assertEqual(len(warnings), 1)
        self.assertIn("b_R1.fq.gz", warnings[0])

    def test_names_without_markers_become_single_runs(self):
        names = ["batch_2024_sample.fastq", "sample_filtered.fastq", "sample_reads.fq"]
        runs, warnings = samples.detect_runs(_paths(names))

        self.assertEqual(
            [run.run_name for run in runs],
            ["batch_2024_sample", "sample_filtered", "sample_reads"],
        )
        self.assertTrue(all(run.pairing == "single" for run in runs))
        self.assertEqual(warnings, [])

    def test_duplicate_run_names_from_different_folders_are_disambiguated(self):
        paths = [
            Path("/data/lane1/s_R1.fq.gz"),
            Path("/data/lane1/s_R2.fq.gz"),
            Path("/data/lane2/s_R1.fq.gz"),
            Path("/data/lane2/s_R2.fq.gz"),
        ]
        runs, warnings = samples.detect_runs(paths)

        self.assertEqual([run.run_name for run in runs], ["lane1_s", "lane2_s"])
        self.assertTrue(all(run.pairing == "paired" for run in runs))
        self.assertEqual(len(warnings), 1)
        self.assertIn("lane1_s", warnings[0])

    def test_empty_input(self):
        self.assertEqual(samples.detect_runs([]), ([], []))


class GroupingTests(unittest.TestCase):
    def test_reported_dataset_groups_into_one_sample_per_prefix(self):
        grouping = samples.build_grouping(_paths(_novogene_names()))

        self.assertEqual(grouping.scheme, "tokens:1")
        self.assertEqual(grouping.aliases, ["AC79", "AC80", "AC81"])
        self.assertEqual(len(grouping.runs), 6)
        self.assertEqual(len(grouping.files), 12)
        self.assertEqual(grouping.pairing, "paired")
        self.assertEqual(grouping.warnings, ())
        self.assertTrue(all(len(sample.runs) == 2 for sample in grouping.samples))
        self.assertTrue(all(sample.file_count == 4 for sample in grouping.samples))

    def test_assembly_style_extensions_give_one_sample_per_file(self):
        grouping = samples.build_grouping(
            _paths(["reads.fastq.gz", "genome.fasta", "transcript.fa.gz", "sequence.embl"])
        )

        self.assertEqual(grouping.aliases, ["genome", "reads", "sequence", "transcript"])
        self.assertEqual(grouping.pairing, "single")

    def test_alias_keeps_the_case_used_in_the_file_name(self):
        grouping = samples.build_grouping(_paths(["AC79_L1_1.fq.gz", "AC79_L1_2.fq.gz"]))

        self.assertEqual(grouping.aliases, ["AC79_L1"])

    def test_lane_fields_are_collapsed_for_a_single_sample(self):
        grouping = samples.build_grouping(_paths(["SampleX_L001.fastq.gz", "SampleX_L002.fastq.gz"]))

        self.assertEqual(grouping.aliases, ["SampleX"])
        self.assertEqual(len(grouping.samples[0].runs), 2)

    def test_shared_prefix_is_not_mistaken_for_the_sample_name(self):
        grouping = samples.build_grouping(
            _paths([
                "sample_AC79_L1_1.fq.gz", "sample_AC79_L1_2.fq.gz",
                "sample_AC80_L1_1.fq.gz", "sample_AC80_L1_2.fq.gz",
            ])
        )

        self.assertEqual(grouping.aliases, ["sample_AC79", "sample_AC80"])

    def test_unrelated_names_stay_one_sample_per_run(self):
        grouping = samples.build_grouping(_paths(["S1_A_R1.fq.gz", "S1_A_R2.fq.gz", "S2_B_R1.fq.gz", "S2_B_R2.fq.gz"]))

        self.assertEqual(grouping.scheme, "stem")
        self.assertEqual(grouping.aliases, ["S1_A", "S2_B"])

    def test_uneven_file_counts_are_reported(self):
        grouping = samples.build_grouping(_paths(["a_R1.fq.gz", "a_R2.fq.gz", "b_R1.fq.gz"]))

        self.assertTrue(any("no mate" in warning for warning in grouping.warnings))
        self.assertTrue(any("Files per sample vary" in warning for warning in grouping.warnings))

    def test_scheme_options_are_ranked_with_the_default_first(self):
        runs, _ = samples.detect_runs(_paths(_novogene_names()))
        options = samples.scheme_options(runs)

        self.assertEqual(options[0].scheme, samples.default_scheme(runs))
        self.assertEqual(options[0].sample_count, 3)
        self.assertEqual(options[0].example_alias, "AC79")
        self.assertEqual(len({option.scheme for option in options}), len(options))
        self.assertIn("stem", [option.scheme for option in options])

    def test_regroup_applies_a_different_depth(self):
        grouping = samples.build_grouping(_paths(_novogene_names()))
        regrouped = samples.regroup(grouping, "stem")

        self.assertEqual(len(regrouped.samples), 6)
        self.assertEqual(len(regrouped.files), 12)

    def test_regroup_with_a_custom_pattern(self):
        grouping = samples.build_grouping(_paths(_novogene_names()))
        regrouped = samples.regroup(grouping, r"regex:^(?P<sample>AC\d+)")

        self.assertEqual(regrouped.aliases, ["AC79", "AC80", "AC81"])

    def test_regroup_with_an_unmatched_pattern_keeps_the_run_name(self):
        grouping = samples.build_grouping(_paths(_novogene_names(("AC79",))))
        regrouped = samples.regroup(grouping, "regex:^(?P<sample>ZZZ)")

        self.assertEqual(len(regrouped.samples), 2)
        self.assertTrue(any("did not match" in warning for warning in regrouped.warnings))

    def test_invalid_pattern_raises_user_error(self):
        grouping = samples.build_grouping(_paths(["a_R1.fq.gz", "a_R2.fq.gz"]))

        with self.assertRaises(UserError):
            samples.regroup(grouping, "regex:[unclosed")

    def test_case_only_alias_collision_is_reported(self):
        grouping = samples.build_grouping(_paths(["AC79_R1.fq.gz", "AC79_R2.fq.gz", "ac79_R1.fq.gz", "ac79_R2.fq.gz"]))

        self.assertTrue(any("capitalisation" in warning for warning in grouping.warnings))


class ReconcileTests(unittest.TestCase):
    def test_aliases_are_matched_case_insensitively(self):
        grouping = samples.build_grouping(_paths(_novogene_names(("AC79", "AC80"))))

        matched, unclaimed = samples.reconcile_aliases(grouping, ["ac79", "AC80"])

        self.assertEqual(len(matched["ac79"]), 2)
        self.assertEqual(len(matched["AC80"]), 2)
        self.assertEqual(unclaimed, [])

    def test_unknown_and_unclaimed_aliases_are_reported(self):
        grouping = samples.build_grouping(_paths(_novogene_names(("AC79", "AC80"))))

        matched, unclaimed = samples.reconcile_aliases(grouping, ["AC79", "AC99"])

        self.assertEqual(matched["AC99"], [])
        self.assertEqual(unclaimed, ["AC80"])


class MappingTsvTests(unittest.TestCase):
    def test_round_trip_preserves_the_grouping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = []
            for name in _novogene_names():
                path = root / name
                path.touch()
                data_files.append(path)
            grouping = samples.build_grouping(data_files)
            mapping = root / "sample_files.tsv"

            samples.write_sample_mapping_tsv(mapping, grouping, root)
            reloaded = samples.read_sample_mapping_tsv(mapping, data_files, root)

        self.assertEqual(reloaded.scheme, "manual")
        self.assertEqual(reloaded.aliases, grouping.aliases)
        self.assertEqual(
            [(run.run_name, run.pairing, run.files) for run in reloaded.runs],
            [(run.run_name, run.pairing, run.files) for run in grouping.runs],
        )
        self.assertEqual(reloaded.warnings, ())

    def test_written_file_has_the_documented_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = [root / "a_R1.fq.gz", root / "a_R2.fq.gz", root / "b.fq.gz"]
            for path in data_files:
                path.touch()
            mapping = root / "sample_files.tsv"
            samples.write_sample_mapping_tsv(mapping, samples.build_grouping(data_files), root)
            lines = mapping.read_text().splitlines()

        self.assertEqual(lines[0], "#sample_files\tv1")
        self.assertEqual(lines[1], "sample_alias\trun_name\tread\tfile")
        self.assertIn("a\ta\t1\ta_R1.fq.gz", lines)
        self.assertIn("a\ta\t2\ta_R2.fq.gz", lines)
        self.assertIn("b\tb\tsingle\tb.fq.gz", lines)

    def test_hand_edited_aliases_are_honoured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = [root / "a_R1.fq.gz", root / "a_R2.fq.gz"]
            for path in data_files:
                path.touch()
            mapping = root / "sample_files.tsv"
            mapping.write_text(
                "#sample_files\tv1\n"
                "sample_alias\trun_name\tread\tfile\n"
                "MySample\trun-42\t1\ta_R1.fq.gz\n"
                "MySample\trun-42\t2\ta_R2.fq.gz\n"
            )
            grouping = samples.read_sample_mapping_tsv(mapping, data_files, root)

        self.assertEqual(grouping.aliases, ["MySample"])
        self.assertEqual(grouping.runs[0].run_name, "run-42")
        self.assertEqual(grouping.runs[0].pairing, "paired")

    def test_dropped_rows_are_reported_as_a_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = [root / "a_R1.fq.gz", root / "a_R2.fq.gz"]
            for path in data_files:
                path.touch()
            mapping = root / "sample_files.tsv"
            mapping.write_text(
                "#sample_files\tv1\n"
                "sample_alias\trun_name\tread\tfile\n"
                "a\ta\t1\ta_R1.fq.gz\n"
            )
            grouping = samples.read_sample_mapping_tsv(mapping, data_files, root)

        self.assertTrue(any("not listed in the mapping" in warning for warning in grouping.warnings))

    def test_unknown_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = [root / "a_R1.fq.gz"]
            data_files[0].touch()
            mapping = root / "sample_files.tsv"
            mapping.write_text(
                "#sample_files\tv1\n"
                "sample_alias\trun_name\tread\tfile\n"
                "a\ta\t1\tnot_discovered.fq.gz\n"
            )

            with self.assertRaises(UserError) as caught:
                samples.read_sample_mapping_tsv(mapping, data_files, root)

        self.assertIn("not_discovered.fq.gz", caught.exception.message)

    def test_run_shared_between_samples_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = [root / "a_R1.fq.gz", root / "a_R2.fq.gz"]
            for path in data_files:
                path.touch()
            mapping = root / "sample_files.tsv"
            mapping.write_text(
                "#sample_files\tv1\n"
                "sample_alias\trun_name\tread\tfile\n"
                "one\tshared\t1\ta_R1.fq.gz\n"
                "two\tshared\t2\ta_R2.fq.gz\n"
            )

            with self.assertRaises(UserError) as caught:
                samples.read_sample_mapping_tsv(mapping, data_files, root)

        self.assertIn("more than one sample", caught.exception.message)

    def test_run_with_three_files_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = [root / f"a_{i}.fq.gz" for i in range(3)]
            for path in data_files:
                path.touch()
            mapping = root / "sample_files.tsv"
            mapping.write_text(
                "#sample_files\tv1\n"
                "sample_alias\trun_name\tread\tfile\n"
                "a\ta\t1\ta_0.fq.gz\n"
                "a\ta\t2\ta_1.fq.gz\n"
                "a\ta\tsingle\ta_2.fq.gz\n"
            )

            with self.assertRaises(UserError) as caught:
                samples.read_sample_mapping_tsv(mapping, data_files, root)

        self.assertIn("lists 3 files", caught.exception.message)

    def test_missing_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_files = [root / "a_R1.fq.gz"]
            data_files[0].touch()
            mapping = root / "sample_files.tsv"
            mapping.write_text("a\ta\t1\ta_R1.fq.gz\n")

            with self.assertRaises(UserError):
                samples.read_sample_mapping_tsv(mapping, data_files, root)


if __name__ == "__main__":
    unittest.main()
