import { useRef, useEffect, useState } from 'react'

/**
 * Animates a number from its previous value to the target using requestAnimationFrame.
 * @param {number} target - The target number to animate towards.
 * @param {number} duration - Animation duration in milliseconds (default 600).
 * @returns {number} The current animated value.
 */
export default function useCountUp(target, duration = 600) {
  const [current, setCurrent] = useState(target)
  const prevRef = useRef(target)
  const rafRef = useRef(null)

  useEffect(() => {
    const from = prevRef.current
    const to = target
    const diff = to - from

    if (Math.abs(diff) < 0.01) {
      setCurrent(to)
      prevRef.current = to
      return
    }

    const startTime = performance.now()

    const animate = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease out cubic for smooth deceleration
      const eased = 1 - Math.pow(1 - progress, 3)
      const value = from + diff * eased

      setCurrent(value)

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate)
      } else {
        setCurrent(to)
        prevRef.current = to
      }
    }

    rafRef.current = requestAnimationFrame(animate)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [target, duration])

  return current
}
