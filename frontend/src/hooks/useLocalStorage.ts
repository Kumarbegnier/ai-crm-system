import { useEffect, useState } from 'react'

export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((val: T) => T)) => void, () => string | null] {
  const [storedValue, setStoredValue] = useState<T>(initialValue)

  useEffect(() => {
    try {
      const item = window.localStorage.getItem(key)
      
      if (item === null) {
        window.localStorage.setItem(key, JSON.stringify(initialValue))
        setStoredValue(initialValue)
      } else {
        setStoredValue(JSON.parse(item))
      }
    } catch (error) {
      console.error('LocalStorage error:', error)
    }
  }, [key, initialValue])

  const setValue = (value: T | ((val: T) => T)) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value
      setStoredValue(valueToStore)
      window.localStorage.setItem(key, JSON.stringify(valueToStore))
    } catch (error) {
      console.error('LocalStorage set error:', error)
    }
  }

  const persist = () => window.localStorage.getItem(key)

  return [storedValue, setValue, persist]
}

