import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scrapers"))
import common, revue


class Classify(unittest.TestCase):
    def test_voies(self):
        c = common.classify_echo
        self.assertEqual(c("Super Maart", "Marché avec phrases en luxembourgeois pour tous", ["fr"])[0], "verifier")
        self.assertEqual(c("Atelier", "Atelier en luxembourgeois", ["lb", "fr"])[0], "confirmé")
        self.assertEqual(c("Rhythmik", "Workshops für Kinder und Eltern", ["lb"])[0], "sauver")
        self.assertIsNone(c("Black Friday", "Soldes", ["fr", "en"])[0])
        self.assertEqual(c("Fest", "Mir feieren haut och mat all deenen déi kommen, fir ëmmer", [])[0], "confirmé")


class Issue(unittest.TestCase):
    def test_roundtrip_and_apply(self):
        items = [{"id": "a" * 12, "title": "T1", "start": "2026-12-01T10:00", "venue": "V", "url": "https://x.lu", "reason": "r", "snippet": "du texte\nsur deux lignes"},
                 {"id": "b" * 12, "title": "T2", "start": "2026-12-02", "venue": "", "url": "", "reason": "r", "snippet": ""}]
        body = revue.body_for("sauver", items, ticked={"b" * 12})
        self.assertEqual([i for _, i in revue.ids_in(body)], ["a" * 12, "b" * 12])
        self.assertEqual([i for m, i in revue.ids_in(body) if m == "x"], ["b" * 12])
        self.assertEqual(body.count("écarter définitivement"), 2)
        self.assertLess(len(revue.body_for("sauver", items * 50)), 65000)
        body2 = body.replace(f"- [ ] <!--no:{'a'*12}-->", f"- [x] <!--no:{'a'*12}-->").replace(f"- [ ] <!--id:{'a'*12}-->", f"- [x] <!--id:{'a'*12}-->")
        with tempfile.TemporaryDirectory() as d:
            revue.DATA = Path(d)
            os.environ.update(ISSUE_BODY=body, ISSUE_LABELS="revue-sauver")
            revue.apply()
            self.assertEqual(json.loads((Path(d) / "revue.json").read_text())["ajouter"], ["b" * 12])
            os.environ["ISSUE_BODY"] = body2
            revue.apply()
            r = json.loads((Path(d) / "revue.json").read_text())
            self.assertEqual(r["ecarter"], ["a" * 12])
            self.assertEqual(r["ajouter"], ["b" * 12])  # écarter l'emporte sur ajouter


class MasterTick(unittest.TestCase):
    def test_tout_ecarter(self):
        items = [{"id": c * 12, "title": c, "start": "2026-12-01", "venue": "", "url": "", "reason": "r", "snippet": ""} for c in "abc"]
        body = revue.body_for("sauver", items)
        self.assertIn("<!--all-->", body)
        self.assertNotIn("<!--all-->", revue.body_for("verifier", items))
        body = body.replace("- [ ] <!--all-->", "- [x] <!--all-->").replace(f"- [ ] <!--id:{'b'*12}-->", f"- [x] <!--id:{'b'*12}-->")
        with tempfile.TemporaryDirectory() as d:
            revue.DATA = Path(d)
            (Path(d) / "revue_queue.json").write_text(json.dumps({"sauver": items + [{"id": "d" * 12}]}))
            os.environ.update(ISSUE_BODY=body, ISSUE_LABELS="revue-sauver")
            revue.apply()
            r = json.loads((Path(d) / "revue.json").read_text())
            self.assertEqual(r["ecarter"], ["a" * 12, "c" * 12, "d" * 12])
            self.assertEqual(r["ajouter"], ["b" * 12])


if __name__ == "__main__":
    unittest.main()
