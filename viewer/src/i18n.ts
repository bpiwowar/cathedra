// The viewer's strings in the deck's language (slide-app's src/i18n.ts):
// `lang` comes from the template (`academic(lang: "fr")`, the text language),
// through the page markers and outline.json. English is the default and the
// fallback for a string or a language not listed.
//
//   t("sb.expand")                       -> "Tout déplier"
//   t("overflow.count", { n: 3 })       -> "3 slides overflow"

type Table = Record<string, string>;

const en: Table = {
  loading: "Loading…",
  close: "Close",
  // structure browser (T)
  "sb.outline": "Outline",
  "sb.expand": "Expand all",
  "sb.collapse": "Collapse all",
  "sb.closeEsc": "Close (Esc)",
  "sb.filter": "Filter: several words, any order (tok bpe)",
  "sb.inDeck": "In the deck:",
  "sb.apply": "OK",
  "sb.applyNote": "Apply the choice (reloads the deck)",
  "sb.only": "Only:",
  "sb.leftOut": "left out of the deck (see “In the deck”)",
  "sb.help": "↑↓ select · → ← open/close · ⏎ go · Esc close · M todo markers",
  "sb.helpDev": " · E edit slide · ⇧E include chain",
  "sb.title": "Title",
  "sb.untitled": "(untitled)",
  "chain.title": "{title}: where it comes from",
  "chain.help": "1–{n} or click to open in VS Code · Esc close",
  // slide types
  "type.todo": "work in progress",
  "type.optional": "optional",
  "type.practical": "practical",
  "type.details": "in detail",
  // help (H)
  "help.home": "Home",
  "help.back": "Back",
  "help.search": "Search (/)",
  "help.none": "Nothing found.",
  "help.noPage": "No page {page}.",
  "help.keysSearch": "↑ ↓ pick · Enter open · Esc clear",
  "help.keys": "/ search · H or Esc close · ⌫ or ← back · Home: contents · API index: docs/api.md",
  // key descriptions (Reveal's ? list)
  "key.help": "Help: writing Typst slides",
  "key.edit": "Edit the slide's source",
  "key.overflow": "Slides that overflow",
  "key.zotero": "Open the slide's Zotero items",
  "key.details": "In detail: open / go back",
  // M
  "todo.hidden": "Work-in-progress markers hidden",
  "todo.shown": "Work-in-progress markers shown",
  // details
  "details.endGroup": "End of the details — I or Esc to go back",
  "details.endTalk": "End of the talk — the details open from their links, or T",
  "details.startGroup": "Start of the details — I or Esc to go back",
  "details.back": "Back to slide {n}",
  "details.none": "No details on this slide",
  "details.pickBack": "Back to which slide?",
  "details.pickOpen": "Which details?",
  // overflow (O)
  "overflow.title": "Slides that overflow",
  "overflow.none": "No slide overflows",
  "overflow.count": "{n} slide(s) overflow",
  "overflow.help": "↑↓ select · ⏎ go · E edit · Esc close",
  "overflow.edit": "edit",
  "overflow.bar": "overflow (O)",
  "overflow.height": "height",
  "overflow.width": "width",
  // Zotero (Z)
  "zotero.none": "No Zotero item on this slide",
  "zotero.devOnly": "Zotero links: dev server only",
  "zotero.pick": "Open in Zotero",
  "zotero.help": "↑↓ or 1–9 select · ⏎ open · Esc close",
  "zotero.figure": "figure",
  "zotero.reference": "reference",
  // picker
  "picker.help": "↑↓ or 1–9 select · ⏎ go · Esc close",
  // dev server
  "dev.disconnected": "Lost the deck server — reconnecting…",
  "dev.reconnected": "Reconnected to the deck server",
  "dev.restarted": "The deck server restarted: reloading",
  "dev.errors": "Typst: {n} error(s)",
  "dev.fixed": "Typst: compiles again",
  "dev.overflows": "{n} slide(s) overflow (O)",
};

const fr: Table = {
  loading: "Chargement…",
  close: "Fermer",
  "sb.outline": "Plan",
  "sb.expand": "Tout déplier",
  "sb.collapse": "Tout replier",
  "sb.closeEsc": "Fermer (Échap)",
  "sb.filter": "Filtrer : plusieurs mots, dans n’importe quel ordre (tok bpe)",
  "sb.inDeck": "Dans la présentation :",
  "sb.apply": "OK",
  "sb.applyNote": "Appliquer le choix (recharge la présentation)",
  "sb.only": "Seulement :",
  "sb.leftOut": "retirée de la présentation (voir « Dans la présentation »)",
  "sb.help": "↑↓ choisir · → ← ouvrir/fermer · ⏎ aller · Échap fermer · M marqueurs « en cours »",
  "sb.helpDev": " · E éditer · ⇧E chaîne d’#include",
  "sb.title": "Titre",
  "sb.untitled": "(sans titre)",
  "chain.title": "{title} : d’où elle vient",
  "chain.help": "1–{n} ou clic pour ouvrir dans VS Code · Échap fermer",
  "type.todo": "en cours",
  "type.optional": "optionnel",
  "type.practical": "TP",
  "type.details": "complément",
  "help.home": "Accueil",
  "help.back": "Retour",
  "help.search": "Rechercher (/)",
  "help.none": "Rien trouvé.",
  "help.noPage": "Pas de page {page}.",
  "help.keysSearch": "↑ ↓ choisir · Entrée ouvrir · Échap effacer",
  "help.keys": "/ rechercher · H ou Échap fermer · ⌫ ou ← retour · Début : sommaire · index de l’API : docs/api.md",
  "key.help": "Aide : écrire des diapositives Typst",
  "key.edit": "Éditer la source de la diapositive",
  "key.overflow": "Diapositives qui débordent",
  "key.zotero": "Ouvrir les références Zotero de la diapositive",
  "key.details": "Compléments : ouvrir / revenir",
  "todo.hidden": "Marqueurs « en cours » masqués",
  "todo.shown": "Marqueurs « en cours » affichés",
  "details.endGroup": "Fin des compléments — I ou Échap pour revenir",
  "details.endTalk": "Fin de la présentation — les compléments s’ouvrent par leurs liens, ou T",
  "details.startGroup": "Début des compléments — I ou Échap pour revenir",
  "details.back": "Retour à la diapositive {n}",
  "details.none": "Pas de complément sur cette diapositive",
  "details.pickBack": "Revenir à quelle diapositive ?",
  "details.pickOpen": "Quel complément ?",
  "overflow.title": "Diapositives qui débordent",
  "overflow.none": "Aucune diapositive ne déborde",
  "overflow.count": "{n} diapositive(s) débordent",
  "overflow.help": "↑↓ choisir · ⏎ aller · E éditer · Échap fermer",
  "overflow.edit": "éditer",
  "overflow.bar": "débordement (O)",
  "overflow.height": "hauteur",
  "overflow.width": "largeur",
  "zotero.none": "Pas de référence Zotero sur cette diapositive",
  "zotero.devOnly": "Liens Zotero : serveur de développement seulement",
  "zotero.pick": "Ouvrir dans Zotero",
  "zotero.help": "↑↓ ou 1–9 choisir · ⏎ ouvrir · Échap fermer",
  "zotero.figure": "figure",
  "zotero.reference": "référence",
  "picker.help": "↑↓ ou 1–9 choisir · ⏎ aller · Échap fermer",
  "dev.disconnected": "Serveur perdu — reconnexion…",
  "dev.reconnected": "Reconnecté au serveur",
  "dev.restarted": "Le serveur a redémarré : rechargement",
  "dev.errors": "Typst : {n} erreur(s)",
  "dev.fixed": "Typst : compile à nouveau",
  "dev.overflows": "{n} diapositive(s) débordent (O)",
};

const tables: Record<string, Table> = { en, fr };

let lang = "en";

/** Set the viewer's language (a Typst `lang`: "fr", "en"…; unknown: English). */
export function setLang(l: string | null | undefined) {
  lang = l && tables[l] ? l : "en";
  document.documentElement.lang = l || "en";
}
export const getLang = () => lang;

/** The string `key` in the deck's language, `{name}` replaced by `vars.name`. */
export function t(key: string, vars: Record<string, string | number> = {}): string {
  const s = tables[lang][key] ?? en[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
}
