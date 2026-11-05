import { useState } from "react"
import type { UseMutationResult } from "@tanstack/react-query"
import { BadgeCheck, Building2, Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import type { Lead } from "@/types/lead"

interface CnpjCardProps {
  lead: Lead
  consultarCnpj: UseMutationResult<unknown, Error, string, unknown>
}

function formatarReais(valor: number | null) {
  if (valor === null || valor === undefined) return null
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })
}

function formatarIdade(meses: number | null) {
  if (meses === null) return null
  if (meses < 12) return `${meses} mes${meses === 1 ? "" : "es"}`
  const anos = Math.floor(meses / 12)
  return `${anos} ano${anos === 1 ? "" : "s"}`
}

/** Consulta o CNPJ na Receita (gratuita, via BrasilAPI) e qualifica poder
 * aquisitivo: MEI ou não, idade da empresa, situação. O Maps não devolve
 * CNPJ - o Eliseu pede ao cliente (é o mesmo dado que vai pro contrato) e
 * cola aqui antes de montar a proposta, pra focar em quem paga sem apertar
 * o orçamento. */
export function CnpjCard({ lead, consultarCnpj }: CnpjCardProps) {
  const [cnpjDigitado, setCnpjDigitado] = useState("")
  const [editando, setEditando] = useState(false)
  const dados = editando ? null : lead.cnpj_dados

  return (
    <div className="space-y-3 rounded-2xl bg-card p-4">
      <h3 className="flex items-center gap-1.5 text-sm font-semibold">
        <Building2 className="size-4 text-primary" />
        CNPJ e poder aquisitivo
      </h3>

      {!dados ? (
        <>
          <p className="text-xs text-muted-foreground">
            O Google Maps não traz CNPJ. Peça ao cliente (é o mesmo dado que vai pro
            contrato) e cole aqui para checar se é MEI e há quanto tempo a empresa existe.
          </p>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (!cnpjDigitado.trim()) return
              consultarCnpj.mutate(cnpjDigitado.trim(), {
                onSuccess: () => {
                  setEditando(false)
                  setCnpjDigitado("")
                },
              })
            }}
          >
            <Input
              value={cnpjDigitado}
              onChange={(e) => setCnpjDigitado(e.target.value)}
              placeholder="00.000.000/0001-00"
              inputMode="numeric"
              className="h-9"
            />
            <Button
              type="submit"
              size="sm"
              disabled={consultarCnpj.isPending || !cnpjDigitado.trim()}
            >
              {consultarCnpj.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <BadgeCheck className="size-4" />
              )}
              Consultar
            </Button>
          </form>
        </>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                dados.mei
                  ? "bg-warning/12 text-warning"
                  : dados.ticket_alto_provavel
                    ? "bg-success/12 text-success"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {dados.mei
                ? "É MEI - ticket tende a ser baixo"
                : dados.ticket_alto_provavel
                  ? "Não é MEI, estabelecida - bom perfil"
                  : "Não é MEI"}
            </span>
            {dados.situacao_cadastral && (
              <span className="text-xs text-muted-foreground">
                {dados.situacao_cadastral}
              </span>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
            {dados.razao_social && (
              <div className="col-span-2">
                <dt className="text-muted-foreground">Razão social</dt>
                <dd className="font-medium">{dados.razao_social}</dd>
              </div>
            )}
            {formatarIdade(dados.idade_meses) && (
              <div>
                <dt className="text-muted-foreground">Tempo de empresa</dt>
                <dd className="font-medium">{formatarIdade(dados.idade_meses)}</dd>
              </div>
            )}
            {formatarReais(dados.capital_social) && (
              <div>
                <dt className="text-muted-foreground">Capital social</dt>
                <dd className="font-medium">{formatarReais(dados.capital_social)}</dd>
              </div>
            )}
            {dados.porte && (
              <div>
                <dt className="text-muted-foreground">Porte</dt>
                <dd className="font-medium">{dados.porte}</dd>
              </div>
            )}
          </dl>

          <button
            type="button"
            onClick={() => setEditando(true)}
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            Consultar outro CNPJ
          </button>
        </div>
      )}
    </div>
  )
}
