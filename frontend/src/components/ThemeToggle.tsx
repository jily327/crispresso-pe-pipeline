import {useEffect, useState} from 'react';
type Theme = 'light' | 'dark';
export function initialTheme():Theme {
  try { return localStorage.getItem('peanalyzer-theme')==='dark'?'dark':'light'; }
  catch { return 'light'; }
}
export function ThemeToggle(){
  const [theme,setTheme]=useState<Theme>(initialTheme);
  useEffect(()=>{document.documentElement.dataset.theme=theme},[theme]);
  return <label className="theme-toggle">Theme<select value={theme} onChange={event=>{
    const next=event.target.value as Theme;setTheme(next);
    try{localStorage.setItem('peanalyzer-theme',next)}catch{/* Preference storage may be disabled. */}
  }}><option value="light">Light</option><option value="dark">Dark</option></select></label>;
}
