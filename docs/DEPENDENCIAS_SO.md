# Dependências e checklist do Linux

A versão Linux inventaria **somente o computador em que o programa foi aberto**. Não varre a rede. O modo para computador pessoal é o **Individual**.

## Checklist

| Item | Estado |
|------|--------|
| Coleta local, planilha e PDF no mesmo desenho do Windows | Feito |
| Exige root, como o Windows exige administrador | Feito |
| Janela gráfica sob `sudo` (acesso da sessão de quem chamou) | Feito |
| Chave do Linux no relatório (licença da distribuição, não chave do Windows) | Feito |
| Hotspot, Bluetooth, câmera, áudio e adaptadores USB no PDF e na planilha | Feito |
| Velocidade do SSD, portas SATA e limite pratico de discos no PDF e na planilha | Feito |
| Campos objetivos de placa-mae, processador, RAM, video e perifericos | Feito |
| Faixa amarela "O que da para melhorar" em cada secao, sem pergunta | Feito |
| Executar pelo código: `sudo -E .venv/bin/python -m hw_inventory` | Feito |
| Gerar `dist/hw-inventory` com PyInstaller | Binário gerado em 14/10/2026. A janela empacotada ainda não foi aberta |
| Um único `.exe` que abra sozinho no Linux e no Windows | **Não é possível.** São dois arquivos, um para cada sistema |

## Pacotes

No Debian, Ubuntu ou Linux Mint:

```bash
sudo apt install python3 python3-tk python3-pip python3-venv dmidecode pciutils util-linux iproute2 x11-xserver-utils iw
```

`dmidecode` precisa de root para série, memória, placa-mãe e slots. `x11-xserver-utils` traz o `xrandr` (monitor e taxa de atualização). `iw` confirma se o Wi-Fi aceita modo ponto de acesso.

O Python do sistema (PEP 668) não aceita `pip install` direto. Na raiz do projeto:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Executar sem empacotar

Na raiz do projeto, a partir do usuário que está na sessão gráfica:

```bash
sudo -E .venv/bin/python -m hw_inventory
```

Não use `sudo hw_inventory`: esse comando não existe. O `-E` preserva a sessão. O programa também procura o acesso gráfico de quem chamou o `sudo` (cookie do LightDM ou `~/.Xauthority` desta máquina).

Sem root, a janela **Privilegios insuficientes** aparece e o programa encerra.

Os arquivos saem na Área de Trabalho de quem chamou o `sudo`, na pasta `Inventario_Patrimonial`.

## Gerar o binário Linux

Isto só funciona **dentro de um Linux** (este PC, uma VM ou WSL2 com interface gráfica). Não gera o `.exe` do Windows.

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Saída: `dist/hw-inventory`. O script não apaga `dist/hw-inventory.exe`.

```bash
sudo -E ./dist/hw-inventory
```

Depois de gerar, falta abrir a janela, preencher o formulário e conferir se a planilha e o PDF saem na Área de Trabalho. Esse teste do binário ainda não foi feito.

## O que a coleta lê

| Informação | Origem neste computador |
|------------|-------------------------|
| Sistema, placa-mãe, BIOS, memória, slots | `dmidecode` e `/sys/class/dmi/id` |
| Processador, clock, caches, bits de endereço | `/proc/cpuinfo` e `/sys/devices/system/cpu` |
| Discos, volumes e velocidade do SSD | `lsblk`, `/proc/mounts` e o enlace PCIe em `/sys/class/nvme` |
| Portas SATA livres (HDD ou outro SSD) | Controlador AHCI em `/sys/class/scsi_host` |
| Vídeo, VRAM e driver | `lspci`, sysfs DRM e `modinfo` |
| Monitores | `xrandr` e EDID em `/sys/class/drm` |
| Rede, tipo Ethernet/Wi-Fi | `/sys/class/net` e `ip` |
| Hotspot | Adaptador em `/sys/class/ieee80211` e modo `AP` no `iw list` |
| Bluetooth, câmera e caixa de som | `/sys/class/bluetooth`, classe USB e placas de som em `/proc/asound` |
| Saídas de áudio | Codec HDA (fone e line-out) e ELD do HDMI |
| Chave do Linux | Licença da distribuição (`copyright` do pacote) ou token Ubuntu Pro, se existir |

Sem root, série da placa, módulos de RAM, soquete do processador e slots PCI ficam como **Nao lido**. A expansão de vídeo e um segundo SSD NVMe em M.2 continuam indeterminados até o `dmidecode` ler os slots. As portas SATA, a velocidade do SSD, o espaço sem partição e o enlace da placa de vídeo não dependem disso.

## O que ainda pode melhorar no relatório

| Limite | Por quê |
|--------|---------|
| Soquetes de RAM, tipo, velocidade e formato de cada módulo | O firmware só entrega isso ao `dmidecode` com root |
| Quantidade de slots PCI vazios e para que servem | Mesma leitura, com `sudo` |
| Soquete do processador para uma troca | Campo `Socket Designation` do `dmidecode` |
| Segundo SSD NVMe em M.2 | O Linux não vê o slot vazio se não houver disco nele; a lista vem dos slots da placa |
| Teto de armazenamento em GB | O firmware desta placa não publica capacidade máxima. O relatório informa as portas livres, não um número inventado |
| Potência da fonte | Não aparece no sistema. Continua na etiqueta da fonte |
| Versão numérica do driver de vídeo AMD | O módulo `amdgpu` não publica `version` no `modinfo` |
| Teste manual da janela empacotada | O binário `dist/hw-inventory` está gerado. Falta abrir com `sudo -E ./dist/hw-inventory` e conferir a pasta `Inventario_Patrimonial` |

## Um executável para Linux e Windows

Não dá para fazer um único arquivo que o Windows e o Linux executem. O `.exe` é um programa Windows. O binário Linux é outro formato. Cada um só abre no sistema em que foi produzido.

O que dá para levar no mesmo pendrive:

| Arquivo | Quem abre |
|---------|-----------|
| `hw-inventory.exe` | Windows, com **Executar como administrador** |
| `hw-inventory` | Linux, com `sudo -E ./hw-inventory` |

A “escolha automática” é o próprio sistema: no Windows a pessoa abre o `.exe`; no Linux abre o arquivo sem extensão. Um `.bat` não roda no Linux, e um `.sh` não é o duplo clique normal no Windows. Por isso são dois atalhos, não um programa só.

O que ainda falta para o executável Linux:

1. **Abrir o binário na sessão gráfica** com `sudo -E ./dist/hw-inventory`, preencher o formulário e conferir a planilha e o PDF em `Inventario_Patrimonial`. O arquivo `dist/hw-inventory` já foi gerado (ELF, 26 MB, 14/10/2026). O teste da janela empacotada ainda não foi feito.
2. **O resultado Linux não se chama `.exe`.** `.exe` é o formato do Windows. No Linux o programa gerado é `hw-inventory`. O `hw-inventory.exe` que já está em `dist/` continua sendo o do Windows e não é recompilado aqui: o fonte daquele programa não está neste repositório.
3. **Não existe um arquivo que os dois sistemas abram.** O pendrive leva os dois. No Windows, botão direito no `.exe`. No Linux, `sudo -E ./hw-inventory`.
