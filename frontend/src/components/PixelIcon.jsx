import { useEffect, useRef } from 'react'
import { drawIcon } from '../game/draw.js'

export default function PixelIcon({ name, size = 32, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    const ctx = ref.current?.getContext('2d')
    if (ctx) drawIcon(ctx, name)
  }, [name])
  return (
    <canvas
      ref={ref}
      width={16}
      height={16}
      aria-hidden="true"
      className={className}
      style={{ width: size, height: size, imageRendering: 'pixelated' }}
    />
  )
}
