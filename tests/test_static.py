from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StaticFallbackTests(unittest.TestCase):
    def test_direct_file_open_loads_assets_and_shows_start_instructions(self):
        web = PROJECT_ROOT / "isdt_monitor" / "web"
        html = (web / "index.html").read_text(encoding="utf-8")
        javascript = (web / "app.js").read_text(encoding="utf-8")
        self.assertIn('href="style.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertIn('window.location.protocol === "file:"', javascript)
        self.assertIn("start.command doppelklicken", javascript)
        self.assertIn('id="hide-inactive"', html)
        self.assertIn("nxhost-hide-inactive", javascript)
        self.assertIn('value="charge_percent_candidate"', html)
        self.assertIn('"charge-progress-fill"', javascript)
        self.assertIn('card.classList.add("charged")', javascript)
        self.assertIn('card.classList.add("charging")', javascript)
        self.assertIn("VOLL GELADEN", javascript)
        self.assertIn("LÄDT", javascript)
        self.assertIn(".charge-progress.complete", (web / "style.css").read_text(encoding="utf-8"))
        self.assertIn("@keyframes charge-shimmer", (web / "style.css").read_text(encoding="utf-8"))
        self.assertIn("Battery Health", javascript)
        self.assertIn("Analyse ausstehend", javascript)
        self.assertIn("measured_capacity_mah", javascript)
        self.assertIn('"selection-label", "● AUSGEWÄHLT"', javascript)
        self.assertIn('card.setAttribute("aria-pressed", String(selected))', javascript)
        self.assertIn(".slot-card.active::before", (web / "style.css").read_text(encoding="utf-8"))
        self.assertIn('id="chart-description"', html)
        self.assertIn("elapsed_seconds_candidate", javascript)
        self.assertIn("bei einem neuen Vorgang beginnt dieser Zähler wieder bei 0", javascript)


if __name__ == "__main__":
    unittest.main()
