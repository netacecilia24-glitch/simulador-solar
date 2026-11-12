# ☀️ Simulador de Posição Solar e Irradiância

Simulador didático em Python (Streamlit) que calcula a posição aparente do Sol
e estima a irradiância solar em um ponto da Terra. Todas as equações estão
implementadas diretamente no código (`solar.py`), **sem pvlib**, e a interface
mostra o passo a passo: fórmula, substituição dos valores e resultado.

## Entradas

- Data
- Horário local (hh:mm)
- Latitude e longitude (graus decimais; Sul e Oeste são negativos)

O fuso horário é identificado automaticamente a partir das coordenadas
(fuso IANA, deslocamento UTC na data informada, incluindo horário de verão, e
meridiano central).

## Equações (nesta ordem)

1. Declinação: `δ = 23,45° · sen[360°(284+n)/365]`
2. Correção da longitude: `CL = 4 · (λ − λ_central)` (min)
3. Equação do tempo: `B = 360°(n−81)/364`; `E = 9,87 sen2B − 7,53 cosB − 1,5 senB` (min)
4. Hora solar verdadeira: `Tsol = Trelógio + (CL + E)/60`
5. Ângulo horário: `h = 15° (Tsol − 12)`
6. Altura solar: `sen α = senφ senδ + cosφ cosδ cos h`
7. Ângulo zenital: `θz = 90° − α`
8. Irradiância extraterrestre normal: `Gon = 1361 [1 + 0,033 cos(360° n/365)]`
9. Irradiância extraterrestre horizontal: `G0h = Gon cosθz`
10. Irradiância no solo (Haurwitz, céu limpo): `GHI = 1098 cosθz exp(−0,059/cosθz)`

> O valor de GHI é uma **estimativa para céu limpo**, não uma medição real.
> Com o Sol abaixo do horizonte, as irradiâncias são zero.

## Como executar localmente

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Implantação no Streamlit Community Cloud

1. Envie esta pasta para um repositório no GitHub (`app.py` na raiz).
2. Em https://share.streamlit.io, clique em **Create app**, escolha o
   repositório e informe `app.py` como arquivo principal.
3. Clique em **Deploy**.

## Estrutura

| Arquivo | Função |
|---|---|
| `app.py` | Interface Streamlit |
| `solar.py` | Equações, fuso horário e passo a passo |
| `requirements.txt` | Dependências |
