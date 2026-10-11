// Translation completeness is a build requirement, never a visitor's network request.
export const LANGUAGES = ['en','ar','de','fr','it','es','pt','tr','ru','ja','zh','ko','hi','ur','id','ms'];
const tokens = text => (text.match(/\{\w+\}|%[sd]/g) || []).sort().join('|');

export function packLocales(data) {
  if (JSON.stringify(data.languages) !== JSON.stringify(LANGUAGES)) throw Error('UI language list mismatch');
  const keys = Object.keys(data.catalog.en), aliases = data.aliases || {}, values = {};
  if (!keys.length) throw Error('Empty UI translation catalog');
  for (const lang of LANGUAGES) {
    const catalog = data.catalog[lang];
    if (!catalog || Object.keys(catalog).length !== keys.length) throw Error('Incomplete UI catalog: ' + lang);
    values[lang] = keys.map(key => {
      const value = catalog[key];
      if (typeof value !== 'string' || !value.trim()) throw Error('Missing UI translation: ' + lang + ' / ' + key);
      if (tokens(key) !== tokens(value)) throw Error('Translation placeholders differ: ' + lang + ' / ' + key);
      return value;
    });
  }
  for (const [alias, key] of Object.entries(aliases)) {
    if (!Object.hasOwn(data.catalog.en, key)) throw Error('Unknown UI alias target: ' + alias);
  }
  // English keys occur once in the browser asset instead of once per language.
  return {version:data.version, languages:LANGUAGES, keys, values, aliases};
}
