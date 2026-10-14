# Inventário patrimonial de hardware

Programa para laboratórios inventariarem **um computador por vez**, de forma simples e **offline**.

O técnico preenche os dados do patrimônio (tombamento, responsável, local etc.), o programa lê as informações do equipamento e gera automaticamente:

- uma **planilha Excel** de inventário  
- um **relatório em PDF**

Os arquivos são salvos na Área de Trabalho, na pasta **`Inventario_Patrimonial`**.

---

## Objetivo

Apoiar o **controle patrimonial** de equipamentos de laboratório:

- registrar qual máquina é o bem (patrimônio + identificação do PC)  
- documentar peças e números de série quando o sistema os exibe  
- gerar evidência em planilha e PDF para arquivo institucional  
- facilitar inventário periódico sem exigir conhecimento de programação  

---

## Ambientes em que o programa pode ser executado

| Ambiente | Neste pacote | Condição |
|----------|--------------|----------|
| **Windows 10 / 11** (64 bits) | **Sim** — `dist/hw-inventory.exe` já pronto | Conta **Administrador** |
| **Linux** | **Sim** — código em `hw_inventory/`; o binário ainda precisa ser gerado | **sudo** |
| **macOS** | Não há versão neste repositório | — |

**Atenção:**

- `dist/hw-inventory.exe` é só Windows. No Linux ele não abre.
- O binário Linux, quando gerado, se chama `dist/hw-inventory` (sem `.exe`). No Windows esse arquivo não abre.
- Não existe um único arquivo que os dois sistemas executem. Cada um precisa do programa feito naquele sistema. A escolha automática é feita por um atalho de cada lado, descrito em [`docs/DEPENDENCIAS_SO.md`](docs/DEPENDENCIAS_SO.md).
- Sem permissão de administrador, o programa não inicia.
- Uso previsto: **um computador por vez**, offline, sem varredura de rede.
- **Active Directory:** na abertura dá para escolher **Individual** ou **AD**. O modo AD só libera com domínio e grupo Administrador. A coleta continua só neste PC.

Detalhes por sistema estão no manual: [`dist/MANUAL_UTILIZACAO.pdf`](dist/MANUAL_UTILIZACAO.pdf).

---

## O que este repositório contém

| Item | Descrição |
|------|-----------|
| `dist/hw-inventory.exe` | Programa pronto para usar no Windows. Não é recompilado por este código |
| `dist/hw-inventory` | Binário Linux gerado por `scripts/build_linux.sh`. A janela ainda não foi testada |
| `hw_inventory/` | Programa Linux (modo local, um computador por vez) |
| `docs/DEPENDENCIAS_SO.md` | Checklist Linux e o que falta para os dois executáveis |
| `dist/MANUAL_UTILIZACAO.pdf` | Manual ilustrado para novos usuários |
| `dist/MANUAL_UTILIZACAO.md` | Mesmo manual em texto |
| `dist/manual_imagens/` | Figuras usadas no manual |

O código publicado aqui é a versão **Linux**. O executável de Windows continua sendo o pacote pronto, sem o fonte daquele sistema. Os dois geram planilha e PDF no mesmo desenho de abas. No Linux, a licença gravada é a da distribuição (neste Mint, GPL-2.0+), não a chave do Windows.

---

## Como utilizar (resumo)

1. Copie para o pendrive: `hw-inventory.exe` + o manual (PDF recomendado).  
2. No PC a inventariar, clique com o **botão direito** em `hw-inventory.exe`.  
3. Escolha **Executar como administrador**.  
4. Se o Windows perguntar se você **permite** o programa, clique em **Sim**.  
5. Preencha o formulário conforme o fluxo (com ou sem tombamento — veja abaixo).  
6. Clique em **Gerar inventario** e aguarde.  
7. Confira os arquivos em:  
   **Área de Trabalho → Inventario_Patrimonial**  
8. No modo Individual o programa **fecha** após **Concluído**. Para o próximo PC, abra o `.exe` nele.

**Importante:** o programa só funciona com conta de **Administrador**.

---

## Telas que o programa abre (nomes oficiais)

| Ordem típica | Nome da tela (título) | Para que serve |
|--------------|----------------------|----------------|
| — | **Privilegios insuficientes** | Aberto sem Administrador — o programa encerra |
| 1 | **Inventário patrimonial · v…** | Escolher **Individual** ou **Active Directory** |
| 1b | **Modo AD autorizado** / **Modo AD indisponível** | Resultado da autorização AD (nível B) |
| 2 | **Inventário patrimonial de hardware · v…** | Formulário dos dados do bem / tombamento |
| 3 | **Sem patrimônio** | Confirmar geração sem número de tombamento |
| 4 | **Gerando inventário** | Coleta e criação da planilha + PDF |
| 5 | **Concluído** | Sucesso e caminho da pasta de saída |
| 6 | **Continuar?** | Apenas modo AD (quando aplicável) |
| — | **Erro** | Falha na coleta |

No **modo Individual**, depois de **Concluído** o programa encerra (não pergunta “outro equipamento”). Para inventariar outro PC, abra o `.exe` naquela máquina.

Também pode aparecer o aviso de segurança do **Windows** (permitir alterações) — isso é do sistema, não do programa.

---

## Fluxos na tela de dados (com e sem tombamento)

Na tela do programa você informa os dados do bem. Há **dois fluxos**:

| | Fluxo A — Com tombamento (recomendado) | Fluxo B — Sem tombamento |
|---|----------------------------------------|---------------------------|
| **Quando usar** | O bem já tem número oficial de patrimônio | Número ainda não existe ou não está disponível |
| **Nº patrimônio** | Preencher | Deixar em branco |
| **Responsável** | Preencher | Preencher |
| **Local** | Preencher | Preencher |
| **Outros campos** | Opcionais (instituição, setor, compra, garantia, NF, status, chave, observações) | Idem |
| **Ao gerar** | Segue direto | O programa pergunta se deseja continuar sem patrimônio |
| **Nome dos arquivos** | `123456_NOME-DO-PC_inventario.xlsx` (e PDF) | `NOME-DO-PC_inventario.xlsx` (e PDF) |
| **No relatório** | Bem identificado pelo patrimônio | Aparece **alerta** de bem sem tombamento |

### Fluxo A — passo a passo

1. Informe o **Nº patrimônio** (tombamento).  
2. Informe **Responsável** e **Local**.  
3. Clique em **Gerar inventario**.  
4. Arquive a planilha e o PDF na pasta institucional.

### Fluxo B — passo a passo

1. Deixe **Nº patrimônio** vazio.  
2. Informe **Responsável** e **Local**.  
3. Clique em **Gerar inventario** e confirme que deseja continuar sem tombamento.  
4. Trate o relatório como **provisório** até a instituição atribuir o número.

Preferência do laboratório: sempre que o bem já estiver tombado, use o **Fluxo A**.

O passo a passo completo, com imagens, está em:

- [`dist/MANUAL_UTILIZACAO.pdf`](dist/MANUAL_UTILIZACAO.pdf)

---

## Requisitos

### Windows (pacote deste repositório)

- Windows 10 ou 11 (64 bits)  
- Conta com permissão de administrador  
- Não é necessário instalar outros programas  

### Linux / macOS

- Versão do programa preparada para aquele sistema  
- Permissão de administrador (`sudo`)  
- Ver o manual de utilização para o passo a passo  

**Executar no Linux** (na raiz do projeto):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo -E .venv/bin/python -m hw_inventory
```

O programa, quando roda como root, procura sozinho o acesso gráfico da sessão de quem chamou o `sudo`.

**Gerar o binário Linux** (só dentro de um Linux):

1. Siga o checklist em [`docs/DEPENDENCIAS_SO.md`](docs/DEPENDENCIAS_SO.md).
2. Depois:

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Saída: `dist/hw-inventory` (não é `.exe` e não substitui o `.exe` do Windows). Uso: `sudo -E ./dist/hw-inventory`.

O binário `dist/hw-inventory` já foi gerado. A janela empacotada ainda não foi testada.

---

## Arquivos gerados

Pasta padrão:

```text
Área de Trabalho\Inventario_Patrimonial\
```

**Com tombamento (Fluxo A):**

```text
123456_NOME-DO-PC_inventario.xlsx
123456_NOME-DO-PC_relatorio_hardware.pdf
```

**Sem tombamento (Fluxo B):**

```text
NOME-DO-PC_inventario.xlsx
NOME-DO-PC_relatorio_hardware.pdf
```

---

## Boas práticas

- Prefira sempre informar o **número de patrimônio** quando o bem já estiver tombado.  
- Guarde cópia dos relatórios na pasta institucional do laboratório.  
- No Linux, o campo **Chave do Linux** traz a licença da distribuição. Se alguém digitar outra chave, ou se houver token de assinatura, trate o arquivo como documento sensível.  
- Não compartilhe relatórios sensíveis por e-mail aberto.

---

## Problemas comuns

| Situação | O que fazer |
|----------|-------------|
| Pediu administrador | No Windows: botão direito → **Executar como administrador**. No Linux: `sudo -E` |
| `sudo: hw_inventory: comando não encontrado` | Use `sudo -E .venv/bin/python -m hw_inventory` na pasta do projeto |
| Janela não abre no Linux (`couldn't connect to display`) | Rode de novo com `sudo -E` a partir do usuário gráfico, não de um terminal sem sessão |
| Windows bloqueia o arquivo | Propriedades → **Desbloquear** |
| Não encontra os arquivos | Área de Trabalho do usuário logado → `Inventario_Patrimonial` |
| PDF “não atualizou” | Feche o PDF aberto e gere novamente |

---

## Contato / uso institucional

Dúvidas sobre tombamento, etiquetas físicas ou arquivamento dos relatórios devem ser tratadas com o **responsável técnico do laboratório** ou a área de patrimônio da instituição.
