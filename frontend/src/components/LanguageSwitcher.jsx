import React from 'react';
import { useT } from '../i18n/LanguageContext';

export function LanguageSwitcher() {
  const { lang, setLang } = useT();

  return (
    <div className="lang-switcher" role="group" aria-label="Language / שפה">
      <button
        className={`lang-btn${lang === 'he' ? ' active' : ''}`}
        onClick={() => setLang('he')}
        aria-pressed={lang === 'he'}
      >
        עב
      </button>
      <button
        className={`lang-btn${lang === 'en' ? ' active' : ''}`}
        onClick={() => setLang('en')}
        aria-pressed={lang === 'en'}
      >
        EN
      </button>
    </div>
  );
}
