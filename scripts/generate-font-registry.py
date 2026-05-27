"""Generate font-registry.v1.yaml from embedded family definitions."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

INTER = {
    "w300": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuOKfAZ9hjQ.ttf",
    "w400": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfAZ9hjQ.ttf",
    "w500": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuFuYAZ9hjQ.ttf",
    "w700": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuFuYAZ9hjQ.ttf",
}
TEX = "https://mirrors.ibiblio.org/CTAN/fonts/tex-gyre/opentype/"


def gw(
    id_: str,
    keys: list[str],
    pubspec: str,
    slug: str,
    *,
    profile: str = "google_direct_default",
    sub: str | None = None,
    pri: str = "P0",
) -> dict:
    strategy = "google_substitute" if sub and sub != pubspec else "google_direct"
    return {
        "id": id_,
        "keys": keys,
        "pubspec_family": pubspec,
        "strategy": strategy,
        "gwfh_slug": slug,
        "profile_id": profile,
        "priority": pri,
        "substitute_name": sub or pubspec,
    }


def noto(id_: str, keys: list[str], pubspec: str, slug: str, *, pri: str = "P2") -> dict:
    return {
        "id": id_,
        "keys": keys,
        "pubspec_family": pubspec,
        "strategy": "noto_fallback",
        "gwfh_slug": slug,
        "profile_id": "cjk_noto",
        "priority": pri,
        "substitute_name": pubspec,
    }


def main() -> None:
    families = [
        {
            "id": "helvetica_neue",
            "keys": ["helvetica neue", "helveticaneue", "helvetica-neue"],
            "pubspec_family": "Helvetica Neue",
            "strategy": "bundled",
            "profile_id": "helvetica_substitute",
            "priority": "P0",
            "substitute_name": "Inter",
            "bundled_weights": {
                "w300": {
                    "url": INTER["w300"],
                    "weight": 300,
                    "asset_name": "helvetica_neue_300.ttf",
                },
                "w400": {
                    "url": INTER["w400"],
                    "weight": 400,
                    "asset_name": "helvetica_neue_400.ttf",
                },
                "w500": {
                    "url": INTER["w500"],
                    "weight": 500,
                    "asset_name": "helvetica_neue_500.ttf",
                },
                "w600": {
                    "url": f"{TEX}texgyreheros-bold.otf",
                    "weight": 600,
                    "asset_name": "helvetica_neue_600.otf",
                },
                "w700": {
                    "url": INTER["w700"],
                    "weight": 700,
                    "asset_name": "helvetica_neue_700.ttf",
                },
                "w400i": {
                    "url": f"{TEX}texgyreheros-italic.otf",
                    "weight": 400,
                    "asset_name": "helvetica_neue_400_italic.otf",
                    "style": "italic",
                },
                "w700i": {
                    "url": f"{TEX}texgyreheros-bolditalic.otf",
                    "weight": 700,
                    "asset_name": "helvetica_neue_700_italic.otf",
                    "style": "italic",
                },
            },
        },
        {
            "id": "helvetica",
            "keys": ["helvetica", "helveticamt", "helvetica regular"],
            "pubspec_family": "Helvetica Neue",
            "strategy": "bundled",
            "profile_id": "helvetica_substitute",
            "priority": "P0",
            "substitute_name": "Inter",
            "bundled_weights": {
                "w300": {
                    "url": INTER["w300"],
                    "weight": 300,
                    "asset_name": "helvetica_neue_300.ttf",
                },
                "w400": {
                    "url": INTER["w400"],
                    "weight": 400,
                    "asset_name": "helvetica_neue_400.ttf",
                },
                "w500": {
                    "url": INTER["w500"],
                    "weight": 500,
                    "asset_name": "helvetica_neue_500.ttf",
                },
                "w700": {
                    "url": INTER["w700"],
                    "weight": 700,
                    "asset_name": "helvetica_neue_700.ttf",
                },
            },
        },
        {
            "id": "sf_pro_text",
            "keys": ["sf pro text", "sfprotext", ".sf ns text", ".sfnstext"],
            "pubspec_family": "SF Pro Text",
            "strategy": "google_substitute",
            "gwfh_slug": "inter",
            "profile_id": "system_ui_sans",
            "priority": "P0",
            "substitute_name": "Inter",
        },
        {
            "id": "sf_pro_display",
            "keys": [
                "sf pro display",
                "sfprodisplay",
                "san francisco display",
                "sanfranciscodisplay",
            ],
            "pubspec_family": "SF Pro Display",
            "strategy": "google_substitute",
            "gwfh_slug": "inter-tight",
            "profile_id": "system_ui_sans",
            "priority": "P0",
            "substitute_name": "Inter Tight",
        },
        {
            "id": "sf_pro",
            "keys": ["san francisco", "sfpro", "sf pro"],
            "pubspec_family": "SF Pro Text",
            "strategy": "google_substitute",
            "gwfh_slug": "inter",
            "profile_id": "system_ui_sans",
            "priority": "P0",
            "substitute_name": "Inter",
        },
        gw("roboto", ["roboto", "roboto-regular", "roboto regular"], "Roboto", "roboto"),
        gw("inter", ["inter", "inter-regular", "inter variable"], "Inter", "inter"),
        gw("arial", ["arial", "arialmt", "arial mt"], "Arial", "arimo", sub="Arimo"),
        gw("open_sans", ["open sans", "opensans", "open sans regular"], "Open Sans", "open-sans"),
        gw("poppins", ["poppins", "poppins regular"], "Poppins", "poppins"),
        gw("montserrat", ["montserrat", "montserrat-regular"], "Montserrat", "montserrat"),
        gw("lato", ["lato", "lato regular"], "Lato", "lato"),
        gw("nunito", ["nunito", "nunito-regular"], "Nunito", "nunito"),
        gw(
            "playfair_display",
            ["playfair display", "playfairdisplay"],
            "Playfair Display",
            "playfair-display",
        ),
        {
            "id": "georgia",
            "keys": ["georgia", "georgiabt", "georgia regular"],
            "pubspec_family": "Georgia",
            "strategy": "google_substitute",
            "gwfh_slug": "gelasio",
            "profile_id": "georgia_gelasio",
            "priority": "P0",
            "substitute_name": "Gelasio",
        },
        gw(
            "times_new_roman",
            ["times new roman", "timesnewroman"],
            "Times New Roman",
            "tinos",
            sub="Tinos",
        ),
        gw("times", ["times", "times mt"], "Times New Roman", "tinos", sub="Tinos"),
        gw("courier_new", ["courier new", "couriernew"], "Courier New", "cousine", sub="Cousine"),
        {
            "id": "segoe_ui",
            "keys": ["segoe ui", "segoeui"],
            "pubspec_family": "Segoe UI",
            "strategy": "google_substitute",
            "gwfh_slug": "open-sans",
            "profile_id": "segoe_selawik",
            "priority": "P0",
            "substitute_name": "Open Sans",
        },
        gw(
            "avenir", ["avenir", "avenirnext"], "Avenir", "nunito-sans", sub="Nunito Sans", pri="P1"
        ),
        gw(
            "avenir_next",
            ["avenir next", "avenir next regular"],
            "Avenir Next",
            "nunito-sans",
            sub="Nunito Sans",
            pri="P1",
        ),
        gw("futura", ["futura", "futura-regular"], "Futura", "jost", sub="Jost", pri="P1"),
        gw(
            "gill_sans",
            ["gill sans", "gillsans", "gill sans mt"],
            "Gill Sans",
            "libre-franklin",
            sub="Libre Franklin",
            pri="P1",
        ),
        gw("verdana", ["verdana", "verdana regular"], "Verdana", "arimo", sub="Arimo", pri="P1"),
        gw(
            "trebuchet_ms",
            ["trebuchet ms", "trebuchetms"],
            "Trebuchet MS",
            "mulish",
            sub="Mulish",
            pri="P1",
        ),
        gw(
            "proxima_nova",
            ["proxima nova", "proximanova"],
            "Proxima Nova",
            "figtree",
            sub="Figtree",
            pri="P1",
        ),
        gw(
            "circular",
            ["circular", "circular std"],
            "Circular",
            "plus-jakarta-sans",
            sub="Plus Jakarta Sans",
            pri="P1",
        ),
        gw(
            "gotham",
            ["gotham", "gotham-medium"],
            "Gotham",
            "montserrat",
            sub="Montserrat",
            pri="P1",
        ),
        gw("din", ["din", "din alternate"], "DIN", "barlow", sub="Barlow", pri="P1"),
        gw(
            "brandon_grotesque",
            ["brandon grotesque", "brandongrotesque"],
            "Brandon Grotesque",
            "josefin-sans",
            sub="Josefin Sans",
            pri="P1",
        ),
        gw("rubik", ["rubik", "rubik regular"], "Rubik", "rubik", pri="P1"),
        gw("manrope", ["manrope", "manrope-regular"], "Manrope", "manrope", pri="P1"),
        gw("work_sans", ["work sans", "worksans"], "Work Sans", "work-sans", pri="P1"),
        gw(
            "calibri", ["calibri", "calibri-regular"], "Calibri", "carlito", sub="Carlito", pri="P1"
        ),
        gw("tahoma", ["tahoma", "tahomaregular"], "Tahoma", "arimo", sub="Arimo", pri="P1"),
        gw(
            "product_sans",
            ["product sans", "productsans"],
            "Product Sans",
            "readex-pro",
            sub="Readex Pro",
            pri="P1",
        ),
        gw(
            "google_sans",
            ["google sans", "googlesans"],
            "Google Sans",
            "readex-pro",
            sub="Readex Pro",
            pri="P1",
        ),
        noto("pingfang_sc", ["pingfang sc", "pingfangsc"], "PingFang SC", "noto-sans-sc"),
        noto("pingfang_tc", ["pingfang tc", "pingfangtc"], "PingFang TC", "noto-sans-tc"),
        noto(
            "hiragino_sans",
            ["hiragino sans", "hiraginokakugothic"],
            "Hiragino Sans",
            "noto-sans-jp",
        ),
        noto("noto_sans_cjk", ["noto sans cjk", "notosanscjk"], "Noto Sans CJK", "noto-sans-jp"),
        noto("noto_naskh", ["noto naskh", "notonaskharabic"], "Noto Naskh", "noto-naskh-arabic"),
        gw(
            "sf_mono",
            ["sf mono", "sfmono-regular"],
            "SF Mono",
            "jetbrains-mono",
            sub="JetBrains Mono",
            pri="P2",
        ),
        gw("fira_code", ["fira code", "firacode"], "Fira Code", "fira-code", pri="P2"),
        gw(
            "jetbrains_mono",
            ["jetbrains mono", "jetbrainsmono"],
            "JetBrains Mono",
            "jetbrains-mono",
            pri="P2",
        ),
        gw("roboto_mono", ["roboto mono", "robotomono"], "Roboto Mono", "roboto-mono", pri="P2"),
        gw("pt_sans", ["pt sans", "ptsans"], "PT Sans", "pt-sans", pri="P2"),
        gw("pt_serif", ["pt serif", "ptserif"], "PT Serif", "pt-serif", pri="P2"),
        gw("oswald", ["oswald", "oswald-regular"], "Oswald", "oswald", pri="P2"),
        gw(
            "merriweather",
            ["merriweather", "merriweather-regular"],
            "Merriweather",
            "merriweather",
            pri="P2",
        ),
        gw("bitter", ["bitter", "bitter-regular"], "Bitter", "bitter", pri="P2"),
        gw("crimson_text", ["crimson text", "crimson"], "Crimson Text", "crimson-text", pri="P2"),
        gw("raleway", ["raleway", "raleway-regular"], "Raleway", "raleway", pri="P2"),
        gw("dm_sans", ["dm sans", "dmsans"], "DM Sans", "dm-sans", pri="P2"),
        gw(
            "plus_jakarta",
            ["plus jakarta sans", "plusjakartasans"],
            "Plus Jakarta Sans",
            "plus-jakarta-sans",
            pri="P2",
        ),
        gw("figtree", ["figtree", "figtree-regular"], "Figtree", "figtree", pri="P2"),
        gw("jost", ["jost", "jost-regular"], "Jost", "jost", pri="P2"),
        gw("anton", ["anton", "anton-regular"], "Anton", "anton", pri="P2"),
        gw("bebas_neue", ["bebas neue", "bebasneue"], "Bebas Neue", "bebas-neue", pri="P2"),
        gw("cinzel", ["cinzel", "cinzel-regular"], "Cinzel", "cinzel", pri="P2"),
        gw("archivo", ["archivo", "archivo-regular"], "Archivo", "archivo", pri="P2"),
        gw("lobster", ["lobster", "lobster-regular"], "Lobster", "lobster", pri="P2"),
        gw("pacifico", ["pacifico", "pacifico-regular"], "Pacifico", "pacifico", pri="P2"),
        gw("great_vibes", ["great vibes", "greatvibes"], "Great Vibes", "great-vibes", pri="P2"),
        gw(
            "sacramento", ["sacramento", "sacramento-regular"], "Sacramento", "sacramento", pri="P2"
        ),
        gw(
            "lucida_grande",
            ["lucida grande", "lucida"],
            "Lucida Grande",
            "open-sans",
            sub="Open Sans",
            pri="P2",
        ),
        gw(
            "consolas",
            ["consolas", "consolas-regular"],
            "Consolas",
            "inconsolata",
            sub="Inconsolata",
            pri="P2",
        ),
        gw(
            "source_sans_pro",
            ["source sans pro", "sourcesanspro"],
            "Source Sans Pro",
            "source-sans-3",
            sub="Source Sans 3",
            pri="P2",
        ),
        gw(
            "source_serif_pro",
            ["source serif pro", "sourceserifpro"],
            "Source Serif Pro",
            "source-serif-4",
            sub="Source Serif 4",
            pri="P2",
        ),
        gw(
            "source_code_pro",
            ["source code pro", "sourcecodepro"],
            "Source Code Pro",
            "source-code-pro",
            pri="P2",
        ),
        gw("cabin", ["cabin", "cabin-regular"], "Cabin", "cabin", pri="P2"),
        gw("oxygen", ["oxygen", "oxygen-regular"], "Oxygen", "oxygen", pri="P2"),
        gw("ubuntu", ["ubuntu", "ubuntu-regular"], "Ubuntu", "ubuntu", pri="P2"),
        gw("fira_sans", ["fira sans", "firasans"], "Fira Sans", "fira-sans", pri="P2"),
        gw(
            "pt_astra_sans",
            ["pt astra sans", "ptastrasans"],
            "PT Astra Sans",
            "pt-sans",
            sub="PT Sans",
            pri="P2",
        ),
        gw(
            "pt_astra_serif",
            ["pt astra serif", "ptastraserif"],
            "PT Astra Serif",
            "pt-serif",
            sub="PT Serif",
            pri="P2",
        ),
        gw(
            "cormorant_garamond",
            ["cormorant garamond", "cormorant"],
            "Cormorant Garamond",
            "cormorant-garamond",
            pri="P2",
        ),
        gw("playfair", ["playfair", "playfair-regular"], "Playfair", "playfair", pri="P2"),
        gw(
            "montserrat_alternates",
            ["montserrat alternates", "montserratalternates"],
            "Montserrat Alternates",
            "montserrat-alternates",
            pri="P2",
        ),
        gw("quicksand", ["quicksand", "quicksand-regular"], "Quicksand", "quicksand", pri="P2"),
        gw(
            "josefin_sans",
            ["josefin sans", "josefinsans"],
            "Josefin Sans",
            "josefin-sans",
            pri="P2",
        ),
        gw("heebo", ["heebo", "heebo-regular"], "Heebo", "heebo", pri="P2"),
        gw("barlow", ["barlow", "barlow-regular"], "Barlow", "barlow", pri="P2"),
        gw("comfortaa", ["comfortaa", "comfortaa-regular"], "Comfortaa", "comfortaa", pri="P2"),
        gw(
            "inconsolata",
            ["inconsolata", "inconsolata-regular"],
            "Inconsolata",
            "inconsolata",
            pri="P2",
        ),
        gw(
            "ibm_plex_sans",
            ["ibm plex sans", "ibmplexsans"],
            "IBM Plex Sans",
            "ibm-plex-sans",
            pri="P2",
        ),
        gw(
            "ibm_plex_serif",
            ["ibm plex serif", "ibmplexserif"],
            "IBM Plex Serif",
            "ibm-plex-serif",
            pri="P2",
        ),
        gw(
            "ibm_plex_mono",
            ["ibm plex mono", "ibmplexmono"],
            "IBM Plex Mono",
            "ibm-plex-mono",
            pri="P2",
        ),
        gw("arimo", ["arimo", "arimo-regular"], "Arimo", "arimo", pri="P2"),
        gw("tinos", ["tinos", "tinos-regular"], "Tinos", "tinos", pri="P2"),
        gw("cousine", ["cousine", "cousine-regular"], "Cousine", "cousine", pri="P2"),
        gw(
            "courier_prime",
            ["courier prime", "courierprime"],
            "Courier Prime",
            "courier-prime",
            pri="P2",
        ),
    ]

    payload = {
        "version": "1.0.4",
        "last_updated": "2026-05-24T22:00:00Z",
        "global_fallback_slug": "noto-sans",
        "normalization_rules": [
            {"id": "strip_mt_suffix", "pattern": "(?i)[-_]?mt$", "replacement": ""},
            {"id": "strip_regular_suffix", "pattern": "(?i)[-_\\s]regular$", "replacement": ""},
            {"id": "clean_spaces", "pattern": "\\s+", "replacement": " "},
        ],
        "profiles": {
            "google_direct_default": {},
            "helvetica_substitute": {
                "download_weight_map": {"w500": "w700"},
                "pubspec_weight_map": {"w500": 500},
                "dart_weight_overrides": {"w500": "w700"},
            },
            "system_ui_sans": {},
            "georgia_gelasio": {},
            "variable_font_axis": {},
            "segoe_selawik": {"dart_weight_overrides": {"w600": "w700"}},
            "cjk_noto": {},
        },
        "families": families,
    }

    out = (
        Path(__file__).resolve().parents[1]
        / "src/figma_flutter_agent/fonts/data/font-registry.v1.yaml"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    with out.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)
    print(f"Wrote {out} with {len(families)} families")


if __name__ == "__main__":
    main()
