import React, { createContext, useContext, useState, useEffect } from 'react';
import { translations } from './translations';

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(
    () => localStorage.getItem('app_lang') || 'he'
  );

  const setLang = (newLang) => {
    setLangState(newLang);
    localStorage.setItem('app_lang', newLang);
    document.documentElement.lang = newLang;
    document.documentElement.dir = newLang === 'he' ? 'rtl' : 'ltr';
    document.title = translations[newLang].app.title;
  };

  // Apply stored preference on first render
  useEffect(() => {
    setLang(lang);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * t(key, vars?) – resolves a dot-separated key from the current locale.
   * Supports simple interpolation: t('projects.tasksRemaining', { count: 5 })
   * Returns the key itself if the translation is missing.
   */
  const t = (key, vars = {}) => {
    const str = key.split('.').reduce((obj, k) => obj?.[k], translations[lang]) ?? key;
    return Object.entries(vars).reduce(
      (s, [k, v]) => s.replace(`{${k}}`, v),
      str
    );
  };

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export const useT = () => useContext(LanguageContext);
