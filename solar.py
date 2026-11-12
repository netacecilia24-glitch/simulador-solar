"""
Cálculos do simulador solar.

Todas as equações são implementadas diretamente aqui (sem pvlib), na ordem
definida no projeto. Os ângulos são tratados em graus; a conversão para
radianos é feita apenas dentro de sind/cosd/asind.
"""
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

GSC = 1361.0  # constante solar (W/m²)


# --------------------------------------------------------------------------
# Trigonometria em graus
# --------------------------------------------------------------------------
def sind(a: float) -> float:
    return math.sin(math.radians(a))


def cosd(a: float) -> float:
    return math.cos(math.radians(a))


def asind(x: float) -> float:
    # limita o argumento a [-1, 1] para evitar erro por arredondamento
    return math.degrees(math.asin(max(-1.0, min(1.0, x))))


# --------------------------------------------------------------------------
# Formatação (vírgula decimal, só na apresentação)
# --------------------------------------------------------------------------
def _limpa(x: float, d: int) -> float:
    return 0.0 if round(x, d) == 0 else x  # evita "-0,00"


def T(x: float, d: int = 2) -> str:
    """Número em texto comum, com vírgula decimal."""
    return f"{_limpa(x, d):.{d}f}".replace(".", ",")


def L(x: float, d: int = 4) -> str:
    """Número em LaTeX, com vírgula decimal."""
    return f"{_limpa(x, d):.{d}f}".replace(".", "{,}")


def P(x: float, d: int = 4) -> str:
    """Número em LaTeX; negativos entre parênteses."""
    s = L(x, d)
    return f"({s})" if _limpa(x, d) < 0 else s


def hms(horas: float) -> str:
    """Horas decimais -> hh:mm:ss."""
    total = round(horas * 3600)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def fill(modelo: str, **valores: str) -> str:
    for k, v in valores.items():
        modelo = modelo.replace(f"<<{k}>>", v)
    return modelo


# --------------------------------------------------------------------------
# Fuso horário
# --------------------------------------------------------------------------
_finder = None


@dataclass
class Fuso:
    nome: str
    deslocamento: float  # horas em relação ao UTC
    meridiano: float  # meridiano central (graus)
    identificado: bool
    avisos: list = field(default_factory=list)


def identificar_fuso(lat: float, lon: float, data: date, hora: time) -> Fuso:
    """Identifica o fuso IANA, o deslocamento UTC na data e o meridiano central."""
    global _finder
    from timezonefinder import TimezoneFinder

    if _finder is None:
        _finder = TimezoneFinder()

    nome = _finder.timezone_at(lat=lat, lng=lon)
    avisos = []

    if nome is None:
        # Sem fuso terrestre (ex.: oceano): estima pelo meridiano mais próximo.
        deslocamento = float(round(lon / 15.0))
        avisos.append(
            "Não há fuso IANA para essas coordenadas (ex.: mar aberto). "
            f"Foi estimado UTC{deslocamento:+.0f} a partir da longitude."
        )
        return Fuso("Estimado pela longitude", deslocamento, deslocamento * 15.0, False, avisos)

    zona = ZoneInfo(nome)
    local = datetime.combine(data, hora, tzinfo=zona)
    deslocamento = local.utcoffset().total_seconds() / 3600.0

    # horário inexistente (adiantamento do horário de verão)?
    volta = local.astimezone(timezone.utc).astimezone(zona)
    if volta.replace(tzinfo=None) != local.replace(tzinfo=None):
        avisos.append(
            "Esse horário não existe nesse dia (mudança de horário de verão). "
            "O deslocamento usado é o anterior à mudança."
        )
    # horário repetido (fim do horário de verão)?
    elif local.replace(fold=1).utcoffset() != local.utcoffset():
        avisos.append(
            "Esse horário ocorre duas vezes nesse dia (fim do horário de verão). "
            "Foi usada a primeira ocorrência."
        )

    return Fuso(nome, deslocamento, deslocamento * 15.0, True, avisos)


# --------------------------------------------------------------------------
# Equações (funções puras, usadas também na curva do dia)
# --------------------------------------------------------------------------
def declinacao(n: int) -> float:
    return 23.45 * sind(360.0 * (284 + n) / 365.0)


def equacao_tempo(n: int) -> float:
    B = 360.0 * (n - 81) / 364.0
    return 9.87 * sind(2 * B) - 7.53 * cosd(B) - 1.5 * sind(B)


def seno_altura(lat: float, delta: float, h: float) -> float:
    return sind(lat) * sind(delta) + cosd(lat) * cosd(delta) * cosd(h)


def irradiancia_extraterrestre_normal(n: int) -> float:
    return GSC * (1 + 0.033 * cosd(360.0 * n / 365.0))


def haurwitz(cosz: float) -> float:
    if cosz <= 0:
        return 0.0
    return 1098.0 * cosz * math.exp(-0.059 / cosz)


# --------------------------------------------------------------------------
# Resultado completo com passo a passo
# --------------------------------------------------------------------------
@dataclass
class Etapa:
    titulo: str
    formula: str  # LaTeX
    substituicao: str  # LaTeX
    resultado: str  # texto


@dataclass
class Resultado:
    data: date
    hora: time
    lat: float
    lon: float
    fuso: Fuso
    n: int
    delta: float
    cl: float
    B: float
    E: float
    t_rel: float
    t_sol_bruto: float
    t_sol: float
    dias_deslocados: int
    h: float
    alpha: float
    theta: float
    cosz: float
    gon: float
    g0h: float
    ghi: float
    acima_horizonte: bool
    etapas: list
    avisos: list


def calcular(data: date, hora: time, lat: float, lon: float, fuso: Fuso) -> Resultado:
    n = data.timetuple().tm_yday
    avisos = list(fuso.avisos)

    # ETAPA 1 — declinação solar
    arg_delta = 360.0 * (284 + n) / 365.0
    delta = declinacao(n)

    # ETAPA 2 — correção da longitude
    cl = 4.0 * (lon - fuso.meridiano)

    # ETAPA 3 — equação do tempo
    B = 360.0 * (n - 81) / 364.0
    E = equacao_tempo(n)

    # ETAPA 4 — hora solar verdadeira
    t_rel = hora.hour + hora.minute / 60.0 + hora.second / 3600.0
    t_sol_bruto = t_rel + (cl + E) / 60.0
    dias_deslocados = math.floor(t_sol_bruto / 24.0)  # -1, 0 ou +1
    t_sol = t_sol_bruto - 24.0 * dias_deslocados
    if dias_deslocados != 0:
        sentido = "seguinte" if dias_deslocados > 0 else "anterior"
        avisos.append(
            f"A correção levou a hora solar para o dia {sentido} ao informado. "
            "A hora solar foi normalizada para 0–24 h; o dia do ano (n) e a "
            "declinação continuam os da data informada (diferença desprezível)."
        )

    # ETAPA 5 — ângulo horário
    h = 15.0 * (t_sol - 12.0)

    # ETAPA 6 — altura solar
    seno_alpha = seno_altura(lat, delta, h)
    alpha = asind(seno_alpha)

    # ETAPA 7 — ângulo zenital
    theta = 90.0 - alpha
    cosz = cosd(theta)
    acima = alpha > 0

    # ETAPA 8 — irradiância extraterrestre normal
    gon = irradiancia_extraterrestre_normal(n)

    # ETAPA 9 — irradiância extraterrestre horizontal
    g0h = gon * cosz if acima else 0.0

    # ETAPA 10 — Haurwitz (céu limpo)
    ghi = haurwitz(cosz) if acima else 0.0

    if not acima:
        avisos.append("O Sol está abaixo do horizonte: as irradiâncias são zero.")

    etapas = [
        Etapa(
            "Etapa 1 — Declinação solar (δ)",
            r"\delta = 23{,}45^\circ \cdot \sin\!\left[\frac{360^\circ\,(284+n)}{365}\right]",
            fill(
                r"\delta = 23{,}45^\circ \cdot \sin\!\left[\frac{360^\circ\,(284+<<n>>)}{365}\right]"
                r" = 23{,}45^\circ \cdot \sin(<<arg>>^\circ)",
                n=str(n), arg=L(arg_delta),
            ),
            f"n = {n}  →  δ = {T(delta, 4)}°",
        ),
        Etapa(
            "Etapa 2 — Correção da longitude (CL)",
            r"CL = 4\,(\lambda - \lambda_c)",
            fill(
                r"CL = 4\,(<<lon>> - <<mc>>)",
                lon=P(lon), mc=P(fuso.meridiano),
            ),
            f"{fuso.nome}, UTC{fuso.deslocamento:+g}  →  CL = {T(cl, 4)} min",
        ),
        Etapa(
            "Etapa 3 — Equação do tempo (E)",
            r"\begin{aligned} B &= \frac{360^\circ\,(n-81)}{364} \\ "
            r"E &= 9{,}87\,\sin(2B) - 7{,}53\,\cos(B) - 1{,}5\,\sin(B) \end{aligned}",
            fill(
                r"\begin{aligned} B &= \frac{360^\circ\,(<<n>>-81)}{364} = <<B>>^\circ \\ "
                r"E &= 9{,}87\,\sin(<<B2>>^\circ) - 7{,}53\,\cos(<<B>>^\circ) - 1{,}5\,\sin(<<B>>^\circ) \end{aligned}",
                n=str(n), B=P(B), B2=P(2 * B),
            ),
            f"B = {T(B, 4)}°  →  E = {T(E, 4)} min",
        ),
        Etapa(
            "Etapa 4 — Hora solar verdadeira (T_sol)",
            r"T_{sol} = T_{rel\acute{o}gio} + \frac{CL + E}{60}",
            fill(
                r"T_{sol} = <<t>> + \frac{<<cl>> + <<e>>}{60} = <<ts>>\ \mathrm{h}",
                t=L(t_rel), cl=P(cl), e=P(E), ts=P(t_sol_bruto),
            ),
            f"T_relógio = {hms(t_rel)} ({T(t_rel, 4)} h)  →  T_sol = {hms(t_sol)} ({T(t_sol, 4)} h)",
        ),
        Etapa(
            "Etapa 5 — Ângulo horário (h)",
            r"h = 15^\circ \cdot (T_{sol} - 12)",
            fill(r"h = 15^\circ \cdot (<<ts>> - 12)", ts=L(t_sol)),
            f"h = {T(h, 4)}°  ({'manhã (antes do meio-dia solar)' if h < 0 else 'tarde (após o meio-dia solar)' if h > 0 else 'meio-dia solar'})",
        ),
        Etapa(
            "Etapa 6 — Altura solar (α)",
            r"\sin\alpha = \sin\varphi\,\sin\delta + \cos\varphi\,\cos\delta\,\cos h",
            fill(
                r"\begin{aligned} \sin\alpha &= \sin(<<lat>>^\circ)\,\sin(<<d>>^\circ) + "
                r"\cos(<<lat>>^\circ)\,\cos(<<d>>^\circ)\,\cos(<<h>>^\circ) = <<sa>> \\ "
                r"\alpha &= \arcsin(<<sa>>) \end{aligned}",
                lat=P(lat), d=P(delta), h=P(h), sa=P(seno_alpha, 6),
            ),
            f"α = {T(alpha, 4)}°",
        ),
        Etapa(
            "Etapa 7 — Ângulo zenital (θz)",
            r"\theta_z = 90^\circ - \alpha",
            fill(r"\theta_z = 90^\circ - <<a>>", a=P(alpha)),
            f"θz = {T(theta, 4)}°  (cos θz = {T(cosz, 6)})",
        ),
        Etapa(
            "Etapa 8 — Irradiância extraterrestre normal (Gon)",
            r"G_{on} = G_{sc}\left[1 + 0{,}033\,\cos\!\left(\frac{360^\circ\,n}{365}\right)\right]",
            fill(
                r"G_{on} = 1361\left[1 + 0{,}033\,\cos\!\left(\frac{360^\circ \cdot <<n>>}{365}\right)\right]",
                n=str(n),
            ),
            f"Gon = {T(gon, 2)} W/m²",
        ),
        Etapa(
            "Etapa 9 — Irradiância extraterrestre horizontal (G0h)",
            r"G_{0h} = G_{on}\,\cos\theta_z",
            (
                fill(r"G_{0h} = <<g>> \cdot <<c>>", g=L(gon, 2), c=L(cosz, 6))
                if acima
                else r"G_{0h} = 0 \quad (\text{Sol abaixo do horizonte: } \cos\theta_z \le 0)"
            ),
            f"G0h = {T(g0h, 2)} W/m²",
        ),
        Etapa(
            "Etapa 10 — Irradiância estimada no solo (Haurwitz, céu limpo)",
            r"GHI = 1098\,\cos\theta_z\,\exp\!\left[\frac{-0{,}059}{\cos\theta_z}\right]",
            (
                fill(
                    r"GHI = 1098 \cdot <<c>> \cdot \exp\!\left[\frac{-0{,}059}{<<c>>}\right]",
                    c=L(cosz, 6),
                )
                if acima
                else r"GHI = 0 \quad (\text{Sol abaixo do horizonte: } \cos\theta_z \le 0)"
            ),
            f"GHI = {T(ghi, 2)} W/m²  — estimativa para céu limpo, não é uma medição real",
        ),
    ]

    return Resultado(
        data=data, hora=hora, lat=lat, lon=lon, fuso=fuso, n=n, delta=delta,
        cl=cl, B=B, E=E, t_rel=t_rel, t_sol_bruto=t_sol_bruto, t_sol=t_sol,
        dias_deslocados=dias_deslocados, h=h, alpha=alpha, theta=theta,
        cosz=cosz, gon=gon, g0h=g0h, ghi=ghi, acima_horizonte=acima,
        etapas=etapas, avisos=avisos,
    )


def curva_do_dia(n: int, lat: float, passos: int = 289):
    """Altura solar, G0h e GHI ao longo da hora solar (0–24 h) do dia n."""
    delta = declinacao(n)
    gon = irradiancia_extraterrestre_normal(n)
    horas, alturas, g0h, ghi = [], [], [], []
    for i in range(passos):
        t = 24.0 * i / (passos - 1)
        h = 15.0 * (t - 12.0)
        sa = seno_altura(lat, delta, h)
        a = asind(sa)
        cz = sa  # cos(90° − α) = sen α
        horas.append(t)
        alturas.append(a)
        g0h.append(gon * cz if a > 0 else 0.0)
        ghi.append(haurwitz(cz) if a > 0 else 0.0)
    return horas, alturas, g0h, ghi
