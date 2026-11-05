import { ArrowLeft } from "lucide-react"
import { Link } from "react-router-dom"
import { PostList } from "@/components/instagram/PostList"

export function InstagramArquivadosPage() {
  return (
      <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6">
        <Link
          to="/instagram"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Voltar para leads do Instagram
        </Link>

        <div>
          <h2 className="text-xl font-semibold tracking-tight">
            Posts arquivados
          </h2>
          <p className="text-sm text-muted-foreground">
            Posts arquivados ficam fora da lista principal. Você pode
            restaurá-los ou excluí-los definitivamente (o que apaga também
            todos os leads daquele post).
          </p>
        </div>

        <PostList
          postSelecionadoId={null}
          onSelecionarPost={() => {}}
          arquivados
        />
      </main>
  )
}
