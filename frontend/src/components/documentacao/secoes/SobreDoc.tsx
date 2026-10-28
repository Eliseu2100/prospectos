import { X } from "lucide-react"
import { InstagramIcon } from "@/components/icons/InstagramIcon"
import { GitHubIcon } from "@/components/icons/GitHubIcon"
import { DocSection, DocP } from "@/components/documentacao/DocSection"

const LINKS = [
  {
    label: "X (Twitter)",
    url: "https://x.com/nandoodev3",
    icone: X,
  },
  {
    label: "Instagram",
    url: "https://www.instagram.com/nandoodev/",
    icone: InstagramIcon,
  },
  {
    label: "GitHub",
    url: "https://github.com/nando0x",
    icone: GitHubIcon,
  },
]

export function SobreDoc() {
  return (
    <DocSection titulo="Sobre / Contato">
      <DocP>
        Esta ferramenta foi criada para automatizar a prospecção de clientes
        de serviços de criação de sites, combinando Google Maps e Instagram
        num só fluxo de trabalho.
      </DocP>

      <div className="flex flex-col gap-2 pt-2 sm:flex-row">
        {LINKS.map(({ label, url, icone: Icone }) => (
          <a
            key={label}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-2xl bg-card px-4 py-3 text-sm font-medium transition-colors hover:bg-accent/40"
          >
            <Icone className="size-4" />
            {label}
          </a>
        ))}
      </div>
    </DocSection>
  )
}
