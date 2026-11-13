import { useState } from "react"
import { CheckCircle2, Mail, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { useConfigEmail, useSalvarConfigEmail, useTestarConfigEmail } from "@/hooks/useEmail"
import { ROTULO_ESTILO_EMAIL, type ConfigSmtp, type EstiloEmail } from "@/services/emailService"

function FormularioSmtp({ smtp }: { smtp: ConfigSmtp }) {
  const salvar = useSalvarConfigEmail()
  const testar = useTestarConfigEmail()
  const [host, setHost] = useState(smtp.host)
  const [porta, setPorta] = useState(String(smtp.porta || 587))
  const [usuario, setUsuario] = useState(smtp.usuario)
  const [senha, setSenha] = useState("")
  const [remetenteNome, setRemetenteNome] = useState(smtp.remetente_nome)
  const [remetenteEmail, setRemetenteEmail] = useState(smtp.remetente_email)
  const [limite, setLimite] = useState(String(smtp.limite_diario || 30))
  const [assinatura, setAssinatura] = useState(smtp.assinatura)
  const [anexarPdf, setAnexarPdf] = useState(smtp.anexar_pdf)
  const [primeiroSimples, setPrimeiroSimples] = useState(smtp.primeiro_simples)
  const [emailTeste, setEmailTeste] = useState("")
  const [estiloTeste, setEstiloTeste] = useState<EstiloEmail>("simples")

  const pronto = smtp.senha_configurada && Boolean(smtp.host) && Boolean(smtp.remetente_email)
  const camposValidos = host.trim() && usuario.trim() && remetenteEmail.trim() && Number(porta) > 0

  function aoSalvar() {
    salvar.mutate(
      {
        host: host.trim(),
        porta: Number(porta),
        usuario: usuario.trim(),
        ...(senha ? { senha } : {}),
        remetente_nome: remetenteNome.trim(),
        remetente_email: remetenteEmail.trim(),
        limite_diario: Number(limite) || 30,
        assinatura,
        anexar_pdf: anexarPdf,
        primeiro_simples: primeiroSimples,
      },
      { onSuccess: () => setSenha("") }
    )
  }

  return (
    <div className="flex flex-col gap-4 rounded-2xl bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Mail className="size-4 text-muted-foreground" />
          <h3 className="font-medium">Envio por SMTP</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
            Hoje: {smtp.enviados_hoje}/{smtp.limite_diario}
          </span>
          {pronto ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-medium text-success">
              <CheckCircle2 className="size-3.5" />
              Pronto
            </span>
          ) : (
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              Não configurado
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1.5 lg:col-span-2">
          <Label htmlFor="smtp-host">Servidor (host)</Label>
          <Input id="smtp-host" value={host} onChange={(e) => setHost(e.target.value)} placeholder="smtp.seudominio.com" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="smtp-porta">Porta</Label>
          <Input id="smtp-porta" type="number" value={porta} onChange={(e) => setPorta(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="smtp-limite">Limite por dia</Label>
          <Input id="smtp-limite" type="number" min={1} value={limite} onChange={(e) => setLimite(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="smtp-usuario">Usuário</Label>
          <Input id="smtp-usuario" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="off" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="smtp-senha">Senha</Label>
          <Input
            id="smtp-senha"
            type="password"
            autoComplete="new-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            placeholder={smtp.senha_configurada ? `Salva · ${smtp.senha_mascarada ?? "••••••••"}` : "Senha do e-mail"}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="smtp-nome">Nome do remetente</Label>
          <Input id="smtp-nome" value={remetenteNome} onChange={(e) => setRemetenteNome(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="smtp-email">E-mail do remetente</Label>
          <Input
            id="smtp-email"
            type="email"
            value={remetenteEmail}
            onChange={(e) => setRemetenteEmail(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="smtp-assinatura">Linha abaixo do nome na assinatura</Label>
        <Textarea
          id="smtp-assinatura"
          rows={1}
          value={assinatura}
          onChange={(e) => setAssinatura(e.target.value)}
          placeholder="Criação de Sites Premium"
        />
        <p className="text-xs text-muted-foreground">
          O e-mail sai com o logo no topo, a assinatura da marca (nome, WhatsApp e e-mail) e o pedido de descadastro.
        </p>
      </div>

      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-1 size-4 accent-primary"
          checked={primeiroSimples}
          onChange={(e) => setPrimeiroSimples(e.target.checked)}
        />
        <span>
          Primeiro e-mail de cada empresa em texto simples
          <span className="block text-xs text-muted-foreground">
            Sem logo, banner nem anexo: cai bem mais na caixa de entrada e não em Promoções. O modelo com a marca e o
            PDF saem a partir do segundo e-mail.
          </span>
        </span>
      </label>

      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-1 size-4 accent-primary"
          checked={anexarPdf}
          onChange={(e) => setAnexarPdf(e.target.checked)}
        />
        <span>
          Anexar a proposta em PDF nos e-mails com a marca
          <span className="block text-xs text-muted-foreground">
            {smtp.anexo_pdf_existe
              ? `Arquivo: ${smtp.anexo_pdf}`
              : `Arquivo não encontrado em ${smtp.anexo_pdf}. Copie o PDF para lá.`}
          </span>
        </span>
      </label>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="email"
            value={emailTeste}
            onChange={(e) => setEmailTeste(e.target.value)}
            placeholder="Enviar teste para..."
            className="w-56"
            aria-label="E-mail de destino do teste"
          />
          <select
            value={estiloTeste}
            onChange={(e) => setEstiloTeste(e.target.value as EstiloEmail)}
            className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
            aria-label="Formato do e-mail de teste"
          >
            {(Object.keys(ROTULO_ESTILO_EMAIL) as EstiloEmail[]).map((chave) => (
              <option key={chave} value={chave}>
                {ROTULO_ESTILO_EMAIL[chave]}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="outline"
            disabled={!emailTeste.trim() || !pronto || testar.isPending}
            onClick={() => testar.mutate({ para: emailTeste.trim(), estilo: estiloTeste })}
          >
            <Send className="size-4" />
            {testar.isPending ? "Enviando..." : "Enviar e-mail de teste"}
          </Button>
        </div>
        <Button size="sm" disabled={!camposValidos || salvar.isPending} onClick={aoSalvar}>
          {salvar.isPending ? "Salvando..." : "Salvar"}
        </Button>
      </div>
      {!pronto && (
        <p className="text-xs text-muted-foreground">Salve as configurações antes de enviar o e-mail de teste.</p>
      )}
    </div>
  )
}

export function ConfigSmtpCard() {
  const { data, isLoading } = useConfigEmail()
  if (isLoading || !data) return <Skeleton className="h-64 rounded-2xl" />
  return <FormularioSmtp smtp={data.smtp} />
}
