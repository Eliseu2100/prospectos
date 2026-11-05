import { useEffect, useState } from "react"

/** true/false conforme a media query bate, atualizado ao redimensionar a
 * janela. Usado pra decidir layout (ex.: sidebar sempre recolhida no celular). */
export function useMediaQuery(query: string): boolean {
  const [combina, setCombina] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false
  )

  useEffect(() => {
    const mql = window.matchMedia(query)
    const atualizar = () => setCombina(mql.matches)
    atualizar()
    mql.addEventListener("change", atualizar)
    return () => mql.removeEventListener("change", atualizar)
  }, [query])

  return combina
}
