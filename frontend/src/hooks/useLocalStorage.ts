import { useState, useCallback } from 'react'

export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((val: T) => T)) => void] {
  // Lazy initializer — reads localStorage once at mount, no useEffect flash
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key)
      return item !== null ? (JSON.parse(item) as T) : initialValue
    } catch {
      return initialValue
    }
  })

  const setValue = useCallback((value: T | ((val: T) => T)) => {
    try {
      setStoredValue(prev => {
        const valueToStore = value instanceof Function ? value(prev) : value
        window.localStorage.setItem(key, JSON.stringify(valueToStore))
        return valueToStore
      })
    } catch (error) {
      console.error('LocalStorage set error:', error)
    }
  }, [key])

  return [storedValue, setValue]
}
