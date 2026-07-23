import { useCallback, useEffect, useState } from 'react'

type Theme = 'light' | 'dark'

const STORAGE_KEY = 'ateric-theme'

function currentTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

/** Reads/writes the `dark` class main.tsx sets before first paint (avoids a flash of the wrong theme). */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(currentTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggle }
}
