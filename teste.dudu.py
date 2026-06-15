# -*- coding: utf-8 -*-
"""
A TORRE DOS DEUSES — jogo em pygame com colisão por tiles.

Todos os 5 andares usam EXATAMENTE o mapa do arquivo "mapa 1.csv"
(só muda a cor, as portas, as escadas e os inimigos de cada andar):
  OLIMPO  — chefe final: Zeus (trancado pela Chave do Olimpo)
  CÉU     — inimigos mais fortes (trancado pela Chave do Céu)
  MEIO    — andar inicial; só tem portas e escadas
  INFERNO — inimigos (demônios)
  SUBMUNDO— chefe: Hades; ao morrer solta a Chave do Céu

Toda rodada de inimigos limpa: VIDA CHEIA + uma HABILIDADE nova.
  Inferno  → Investida (C)        Submundo → Fúria de Fogo (Z)
  Céu      → Raio Celestial (X) + 1 coração extra

Controles:
  Setas / WASD  mover
  ESPAÇO        atirar
  E             abrir porta (perto dela)
  C / Shift     Investida    ·    Z  Fúria de Fogo    ·    X  Raio Celestial
  R             reiniciar (após morrer ou vencer)

Rode com:  python "jogo.py"      (teste rápido sem janela: python "jogo.py" --teste)
"""

import csv
import math
import os
import sys

TILE = 24
COLS = 30
ROWS = 30
HUD = 48
LARG = COLS * TILE
ALT_MAPA = ROWS * TILE
ALT = ALT_MAPA + HUD
FPS = 60

# ids de tile do CSV que são parede (colisão)
SOLIDOS = {13, 20, 21, 22, 32, 34, 40, 44, 45, 46}
PASTA = os.path.dirname(os.path.abspath(__file__))

MODO_TESTE = '--teste' in sys.argv
if MODO_TESTE:
    os.environ['SDL_VIDEODRIVER'] = 'dummy'

import pygame  # noqa: E402  (depois de configurar SDL no modo teste)

# paleta de cores por andar: parede, borda da parede, piso claro (18), piso escuro (27)
PALETAS = {
    'meio':     dict(parede=(150, 92, 64), borda=(98, 56, 38), p18=(197, 117, 79), p27=(73, 38, 35)),
    'inferno':  dict(parede=(124, 32, 24), borda=(70, 12, 10), p18=(152, 54, 34), p27=(95, 25, 20)),
    'submundo': dict(parede=(74, 26, 64), borda=(42, 10, 36), p18=(64, 28, 50), p27=(40, 16, 32)),
    'ceu':      dict(parede=(148, 168, 210), borda=(102, 122, 168), p18=(216, 228, 246), p27=(176, 196, 230)),
    'olimpo':   dict(parede=(192, 172, 112), borda=(140, 120, 72), p18=(240, 234, 212), p27=(214, 204, 174)),
}

TIPOS_INIMIGO = {
    'demonio': dict(hp=3,  vel=1.5, dano=1, aggro=190, raio=10, cd_tiro=0,   cor=(200, 50, 40),   nome='Demônio'),
    'anjo':    dict(hp=5,  vel=1.9, dano=1, aggro=250, raio=10, cd_tiro=110, cor=(245, 245, 255), nome='Anjo Caído'),
    'hades':   dict(hp=18, vel=0.8, dano=1, aggro=999, raio=17, cd_tiro=90,  cor=(60, 30, 80),    nome='HADES'),
    'zeus':    dict(hp=30, vel=1.1, dano=1, aggro=999, raio=18, cd_tiro=80,  cor=(250, 245, 220), nome='ZEUS'),
}

NOME_CHAVE = {'chave_ceu': 'Chave do Céu', 'chave_olimpo': 'Chave do Olimpo'}


def tile_px(r, c):
    """centro (em pixels) do tile (linha, coluna)"""
    return c * TILE + TILE // 2, r * TILE + TILE // 2


def carregar_csv(nome):
    grade = []
    with open(os.path.join(PASTA, nome), newline='') as f:
        for linha in csv.reader(f):
            valores = [int(v) for v in linha if v.strip() != '']
            if valores:
                grade.append(valores)
    return grade


class Porta:
    def __init__(self, r, c, chave=None):
        self.r, self.c = r, c
        self.chave = chave          # None = destrancada; senão 'chave_ceu'/'chave_olimpo'
        self.aberta = False

    def rect(self):
        return pygame.Rect(self.c * TILE, self.r * TILE, TILE, TILE)


class Escada:
    def __init__(self, r, c, destino, chegada, tipo):
        self.r, self.c = r, c
        self.destino = destino      # nome do andar
        self.chegada = chegada      # (linha, coluna) onde o jogador aparece
        self.tipo = tipo            # 'desce' ou 'sobe'


class Coletavel:
    def __init__(self, x, y, tipo):
        self.x, self.y, self.tipo = x, y, tipo

    def rect(self):
        return pygame.Rect(int(self.x) - 10, int(self.y) - 10, 20, 20)


class Tiro:
    def __init__(self, x, y, vx, vy, dano, amigo, cor, raio=5):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.dano, self.amigo, self.cor, self.raio = dano, amigo, cor, raio
        self.vida = 260

    def rect(self):
        return pygame.Rect(int(self.x) - self.raio, int(self.y) - self.raio,
                           self.raio * 2, self.raio * 2)


class RaioDoCeu:
    """ataque telegrafado de Zeus: marca o chão e depois cai um raio"""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 55         # frames de aviso
        self.ativo = 0
        self.acertou = False


class Inimigo:
    def __init__(self, x, y, tipo):
        cfg = TIPOS_INIMIGO[tipo]
        self.x, self.y, self.tipo = float(x), float(y), tipo
        self.hp = self.hp_max = cfg['hp']
        self.vel, self.dano = cfg['vel'], cfg['dano']
        self.aggro, self.raio = cfg['aggro'], cfg['raio']
        self.cd_tiro_max = cfg['cd_tiro']
        self.cor, self.nome = cfg['cor'], cfg['nome']
        self.cd_tiro = cfg['cd_tiro']
        self.cd_especial = 160
        self.flash = 0

    def rect(self):
        t = self.raio
        return pygame.Rect(int(self.x) - t, int(self.y) - t, t * 2, t * 2)

    def chefe(self):
        return self.tipo in ('hades', 'zeus')


class Andar:
    def __init__(self, nome, titulo, grade):
        self.nome, self.titulo = nome, titulo
        self.grade = grade
        self.portas = []
        self.escadas = []
        self.inimigos = []
        self.coletaveis = []
        self.tiros = []
        self.raios = []             # ataques de Zeus
        self.recompensa_dada = False


class Jogador:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.w = 18
        self.vel = 3.0
        self.vidas_max = 3
        self.vidas = 3
        self.dir = (0, 1)
        self.invuln = 0
        self.cd_ataque = 0
        self.cd_raio = 0
        self.cd_dash = 0
        self.cd_furia = 0
        self.habilidades = set()    # 'investida', 'furia', 'raio'
        self.chaves = set()

    def rect(self):
        m = self.w // 2
        return pygame.Rect(int(self.x) - m, int(self.y) - m, self.w, self.w)


# ---------------------------------------------------------------- construção

def construir_andares():
    """Todos os andares usam EXATAMENTE o mapa do arquivo "mapa 1.csv";
    só mudam a paleta de cores, as portas, as escadas e os inimigos.
    A sala escura do canto superior esquerdo guarda a escada que DESCE;
    a sala escura do canto inferior direito guarda a escada que SOBE."""
    base = carregar_csv('mapa 1.csv')
    copia = lambda: [linha[:] for linha in base]
    andares = {}

    # ----- MEIO: andar inicial — só portas e escadas
    meio = Andar('meio', 'MEIO — Salão das Portas', copia())
    meio.portas = [
        Porta(10, 7),                       # porta para a sala da escada do Inferno
        Porta(18, 21, 'chave_ceu'),         # portas para a sala da escada do Céu
        Porta(25, 13, 'chave_ceu'),
    ]
    meio.escadas = [
        Escada(4, 4, 'inferno', (5, 3), 'desce'),
        Escada(24, 22, 'ceu', (22, 22), 'sobe'),
    ]
    andares['meio'] = meio

    # ----- INFERNO
    inf = Andar('inferno', 'INFERNO', copia())
    inf.portas = [Porta(10, 7), Porta(18, 21), Porta(25, 13)]
    inf.escadas = [
        Escada(4, 4, 'meio', (6, 4), 'sobe'),
        Escada(24, 22, 'submundo', (22, 22), 'desce'),
    ]
    for r, c in ((13, 5), (15, 12), (16, 20), (21, 7)):
        inf.inimigos.append(Inimigo(*tile_px(r, c), 'demonio'))
    andares['inferno'] = inf

    # ----- SUBMUNDO (chefe Hades)
    sub = Andar('submundo', 'SUBMUNDO — Covil de Hades', copia())
    sub.portas = [Porta(10, 7), Porta(18, 21), Porta(25, 13)]
    sub.escadas = [Escada(24, 22, 'inferno', (22, 22), 'sobe')]
    sub.inimigos.append(Inimigo(*tile_px(14, 10), 'hades'))
    andares['submundo'] = sub

    # ----- CÉU
    ceu = Andar('ceu', 'CÉU', copia())
    ceu.portas = [
        Porta(10, 7, 'chave_olimpo'),       # portão para a escada do Olimpo
        Porta(18, 21),
        Porta(25, 13),
    ]
    ceu.escadas = [
        Escada(24, 22, 'meio', (22, 22), 'desce'),
        Escada(4, 4, 'olimpo', (6, 4), 'sobe'),
    ]
    for r, c in ((12, 5), (13, 20), (16, 10), (21, 8)):
        ceu.inimigos.append(Inimigo(*tile_px(r, c), 'anjo'))
    andares['ceu'] = ceu

    # ----- OLIMPO (chefe final Zeus)
    oli = Andar('olimpo', 'OLIMPO — Trono de Zeus', copia())
    oli.portas = [Porta(10, 7), Porta(18, 21), Porta(25, 13)]
    oli.escadas = [Escada(4, 4, 'ceu', (6, 4), 'desce')]
    oli.inimigos.append(Inimigo(*tile_px(14, 10), 'zeus'))
    andares['olimpo'] = oli

    return andares


# ---------------------------------------------------------------- jogo

class Jogo:
    def __init__(self):
        self.andares = construir_andares()
        self.atual = 'meio'
        self.jogador = Jogador(*tile_px(18, 8))
        self.estado = 'jogando'     # jogando | morto | vitoria
        self.escada_cd = 0
        self.tempo = 0
        self.msgs = []
        self.msg('Bem-vindo! Abra a porta (E) e desça a escada para o Inferno.')

    def andar(self):
        return self.andares[self.atual]

    def msg(self, texto):
        self.msgs.append([texto, 240])

    # -------------------------------------------------- colisão e movimento

    def colide(self, rect, andar=None):
        a = andar or self.andar()
        if rect.left < 0 or rect.top < 0 or rect.right > LARG or rect.bottom > ALT_MAPA:
            return True
        r0, r1 = rect.top // TILE, (rect.bottom - 1) // TILE
        c0, c1 = rect.left // TILE, (rect.right - 1) // TILE
        for r in range(max(r0, 0), min(r1, ROWS - 1) + 1):
            for c in range(max(c0, 0), min(c1, COLS - 1) + 1):
                if a.grade[r][c] in SOLIDOS:
                    return True
        for p in a.portas:
            if not p.aberta and rect.colliderect(p.rect()):
                return True
        return False

    def tentar_mover(self, ent, dx, dy):
        ent.x += dx
        if self.colide(ent.rect()):
            ent.x -= dx
        ent.y += dy
        if self.colide(ent.rect()):
            ent.y -= dy

    # -------------------------------------------------- ações do jogador

    def mudar_andar(self, nome, chegada):
        self.atual = nome
        self.jogador.x, self.jogador.y = tile_px(*chegada)
        self.escada_cd = 25
        self.msg(self.andar().titulo)

    def abrir_porta(self):
        j = self.jogador
        for p in self.andar().portas:
            if p.aberta:
                continue
            px, py = tile_px(p.r, p.c)
            if math.hypot(px - j.x, py - j.y) < 42:
                if p.chave is None or p.chave in j.chaves:
                    p.aberta = True
                    self.andar().grade[p.r][p.c] = 18
                    self.msg('Porta aberta!')
                else:
                    self.msg('Trancada! Você precisa da %s.' % NOME_CHAVE[p.chave])
                return

    def atacar(self):
        """ataque básico: um tiro na direção em que o jogador está olhando"""
        j = self.jogador
        if j.cd_ataque > 0:
            return
        j.cd_ataque = 22
        vx, vy = j.dir[0] * 5.5, j.dir[1] * 5.5
        self.andar().tiros.append(Tiro(j.x, j.y, vx, vy, 1, True, (255, 250, 180), 4))

    def atirar_raio(self):
        j = self.jogador
        if 'raio' not in j.habilidades or j.cd_raio > 0:
            return
        j.cd_raio = 45
        vx, vy = j.dir[0] * 6.5, j.dir[1] * 6.5
        self.andar().tiros.append(Tiro(j.x, j.y, vx, vy, 2, True, (120, 220, 255), 6))

    def investida(self):
        j = self.jogador
        if 'investida' not in j.habilidades or j.cd_dash > 0:
            return
        j.cd_dash = 50
        j.invuln = max(j.invuln, 18)
        for _ in range(16):
            self.tentar_mover(j, j.dir[0] * 3.5, j.dir[1] * 3.5)

    def furia(self):
        j = self.jogador
        if 'furia' not in j.habilidades or j.cd_furia > 0:
            return
        j.cd_furia = 90
        for k in range(8):
            ang = k * math.pi / 4
            self.andar().tiros.append(Tiro(j.x, j.y, math.cos(ang) * 4.0,
                                           math.sin(ang) * 4.0, 1, True, (255, 140, 50), 5))

    def dano_jogador(self, origem_x=None):
        j = self.jogador
        if j.invuln > 0 or self.estado != 'jogando':
            return
        j.vidas -= 1
        j.invuln = 75
        if origem_x is not None:
            empurrao = 14 if j.x >= origem_x else -14
            self.tentar_mover(j, empurrao, 0)
        if j.vidas <= 0:
            self.estado = 'morto'

    def dano_inimigo(self, ini, dano):
        ini.hp -= dano
        ini.flash = 6
        if ini.hp > 0:
            return
        a = self.andar()
        if ini in a.inimigos:
            a.inimigos.remove(ini)
        if ini.tipo == 'hades':
            a.coletaveis.append(Coletavel(ini.x, ini.y, 'chave_ceu'))
            self.msg('Hades caiu! Ele soltou a Chave do Céu.')
        if ini.tipo == 'zeus':
            self.estado = 'vitoria'
            return
        if not a.inimigos and not a.recompensa_dada:
            a.recompensa_dada = True
            self.recompensa_rodada(a)

    # toda rodada de inimigos limpa: vida cheia + habilidade nova
    RECOMPENSAS = {
        'inferno':  ('investida', 'C', 'Investida'),
        'submundo': ('furia', 'Z', 'Fúria de Fogo'),
        'ceu':      ('raio', 'X', 'Raio Celestial'),
    }

    def recompensa_rodada(self, a):
        if a.nome not in self.RECOMPENSAS:
            return
        j = self.jogador
        if a.nome == 'ceu':
            j.vidas_max += 1
            a.coletaveis.append(Coletavel(*tile_px(14, 15), 'chave_olimpo'))
            self.msg('+1 coração! A Chave do Olimpo apareceu no salão.')
        j.vidas = j.vidas_max
        hab, tecla, nome = self.RECOMPENSAS[a.nome]
        j.habilidades.add(hab)
        self.msg('Rodada limpa! Vida cheia + habilidade: %s (tecla %s)' % (nome, tecla))

    # -------------------------------------------------- atualização

    def atualizar(self, teclas):
        if self.estado != 'jogando':
            return
        self.tempo += 1
        j = self.jogador
        a = self.andar()

        dx = (teclas[pygame.K_RIGHT] or teclas[pygame.K_d]) - \
             (teclas[pygame.K_LEFT] or teclas[pygame.K_a])
        dy = (teclas[pygame.K_DOWN] or teclas[pygame.K_s]) - \
             (teclas[pygame.K_UP] or teclas[pygame.K_w])
        if dx or dy:
            j.dir = (dx, dy) if not (dx and dy) else (dx * 0.707, dy * 0.707)
            f = 0.707 if (dx and dy) else 1.0
            self.tentar_mover(j, dx * j.vel * f, dy * j.vel * f)
        if teclas[pygame.K_SPACE]:
            self.atacar()
        if teclas[pygame.K_x]:
            self.atirar_raio()
        if teclas[pygame.K_z]:
            self.furia()

        for nome in ('invuln', 'cd_ataque', 'cd_raio', 'cd_dash', 'cd_furia'):
            v = getattr(j, nome)
            if v > 0:
                setattr(j, nome, v - 1)
        if self.escada_cd > 0:
            self.escada_cd -= 1

        # escadas
        if self.escada_cd == 0:
            r, c = int(j.y) // TILE, int(j.x) // TILE
            for e in a.escadas:
                if (r, c) == (e.r, e.c):
                    self.mudar_andar(e.destino, e.chegada)
                    return

        # coletáveis (chaves)
        for col in list(a.coletaveis):
            if col.rect().colliderect(j.rect()):
                a.coletaveis.remove(col)
                j.chaves.add(col.tipo)
                self.msg('Você pegou a %s!' % NOME_CHAVE[col.tipo])

        # inimigos
        for ini in list(a.inimigos):
            self.atualizar_inimigo(ini, a)

        # tiros
        for t in list(a.tiros):
            t.x += t.vx
            t.y += t.vy
            t.vida -= 1
            morto = t.vida <= 0 or self.colide(t.rect(), a)
            if not morto:
                if t.amigo:
                    for ini in list(a.inimigos):
                        if t.rect().colliderect(ini.rect()):
                            self.dano_inimigo(ini, t.dano)
                            morto = True
                            break
                elif t.rect().colliderect(j.rect()):
                    self.dano_jogador(t.x)
                    morto = True
            if morto and t in a.tiros:
                a.tiros.remove(t)

        # raios de Zeus
        for rz in list(a.raios):
            if rz.t > 0:
                rz.t -= 1
                if rz.t == 0:
                    rz.ativo = 12
            elif rz.ativo > 0:
                rz.ativo -= 1
                if not rz.acertou and math.hypot(j.x - rz.x, j.y - rz.y) < 36:
                    rz.acertou = True
                    self.dano_jogador(rz.x)
                if rz.ativo == 0:
                    a.raios.remove(rz)

        # mensagens
        for m in list(self.msgs):
            m[1] -= 1
            if m[1] <= 0:
                self.msgs.remove(m)

    def atualizar_inimigo(self, ini, a):
        j = self.jogador
        if ini.flash > 0:
            ini.flash -= 1
        dist = math.hypot(j.x - ini.x, j.y - ini.y)
        if dist < ini.aggro and dist > 1:
            ux, uy = (j.x - ini.x) / dist, (j.y - ini.y) / dist
            self.tentar_mover(ini, ux * ini.vel, uy * ini.vel)
        if ini.rect().colliderect(j.rect()):
            self.dano_jogador(ini.x)

        if ini.cd_tiro_max and dist < ini.aggro:
            ini.cd_tiro -= 1
            if ini.cd_tiro <= 0:
                ini.cd_tiro = ini.cd_tiro_max
                ang = math.atan2(j.y - ini.y, j.x - ini.x)
                if ini.tipo == 'anjo':
                    self.tiro_inimigo(a, ini, ang, 3.4, (255, 240, 160))
                elif ini.tipo == 'hades':
                    for desvio in (-0.35, 0.0, 0.35):
                        self.tiro_inimigo(a, ini, ang + desvio, 3.0, (255, 120, 40))
                elif ini.tipo == 'zeus':
                    self.tiro_inimigo(a, ini, ang, 4.5, (170, 220, 255))

        if ini.tipo == 'zeus':
            ini.cd_especial -= 1
            if ini.cd_especial <= 0:
                ini.cd_especial = 160
                # anel de raios + queda de raio em cima do jogador
                for k in range(8):
                    ang = k * math.pi / 4
                    self.tiro_inimigo(a, ini, ang, 2.6, (220, 235, 255))
                a.raios.append(RaioDoCeu(j.x, j.y))

    def tiro_inimigo(self, a, ini, ang, vel, cor):
        a.tiros.append(Tiro(ini.x, ini.y, math.cos(ang) * vel,
                            math.sin(ang) * vel, 1, False, cor))


# ---------------------------------------------------------------- desenho

def desenhar_coracao(s, x, y, t, cor):
    pygame.draw.circle(s, cor, (x - t // 4, y - t // 8), t // 4)
    pygame.draw.circle(s, cor, (x + t // 4, y - t // 8), t // 4)
    pygame.draw.polygon(s, cor, [(x - t // 2 + 1, y), (x + t // 2 - 1, y), (x, y + t // 2)])


def desenhar_chave(s, x, y, cor):
    pygame.draw.circle(s, cor, (x - 4, y), 5, 2)
    pygame.draw.line(s, cor, (x - 1, y), (x + 8, y), 2)
    pygame.draw.line(s, cor, (x + 5, y), (x + 5, y + 4), 2)
    pygame.draw.line(s, cor, (x + 8, y), (x + 8, y + 4), 2)


def desenhar_raio_icone(s, x, y, cor):
    pygame.draw.polygon(s, cor, [(x + 2, y - 8), (x - 5, y + 1), (x - 1, y + 1),
                                 (x - 3, y + 8), (x + 5, y - 2), (x + 1, y - 2)])


class Renderizador:
    def __init__(self):
        self.f_peq = pygame.font.SysFont('arial', 13)
        self.f_med = pygame.font.SysFont('arial', 17, bold=True)
        self.f_grd = pygame.font.SysFont('arial', 42, bold=True)
        self.mapa = pygame.Surface((LARG, ALT_MAPA))

    def desenhar(self, tela, jogo):
        s = self.mapa
        a = jogo.andar()
        pal = PALETAS[a.nome]

        # tiles
        for r in range(ROWS):
            for c in range(COLS):
                v = a.grade[r][c]
                x, y = c * TILE, r * TILE
                if v in SOLIDOS:
                    pygame.draw.rect(s, pal['parede'], (x, y, TILE, TILE))
                    pygame.draw.rect(s, pal['borda'], (x, y, TILE, TILE), 2)
                    pygame.draw.line(s, pal['borda'], (x, y + TILE // 2), (x + TILE, y + TILE // 2))
                else:
                    cor = pal['p18'] if v == 18 else pal['p27']
                    pygame.draw.rect(s, cor, (x, y, TILE, TILE))

        # escadas
        for e in a.escadas:
            x, y = e.c * TILE, e.r * TILE
            base = (40, 40, 48) if e.tipo == 'desce' else (235, 225, 170)
            pygame.draw.rect(s, base, (x + 2, y + 2, TILE - 4, TILE - 4))
            deg = (90, 90, 100) if e.tipo == 'desce' else (180, 165, 110)
            for i in range(3):
                pygame.draw.rect(s, deg, (x + 4, y + 4 + i * 6, TILE - 8, 3))
            seta = (255, 255, 255)
            cx, cy = x + TILE // 2, y + TILE // 2
            if e.tipo == 'desce':
                pygame.draw.polygon(s, seta, [(cx - 5, cy - 4), (cx + 5, cy - 4), (cx, cy + 5)])
            else:
                pygame.draw.polygon(s, seta, [(cx - 5, cy + 4), (cx + 5, cy + 4), (cx, cy - 5)])

        # portas
        for p in a.portas:
            if p.aberta:
                continue
            x, y = p.c * TILE, p.r * TILE
            pygame.draw.rect(s, (92, 58, 26), (x + 1, y + 1, TILE - 2, TILE - 2))
            pygame.draw.rect(s, (50, 30, 12), (x + 1, y + 1, TILE - 2, TILE - 2), 2)
            pygame.draw.circle(s, (230, 200, 90), (x + TILE - 7, y + TILE // 2), 2)
            if p.chave:
                cor = (255, 215, 60) if p.chave == 'chave_ceu' else (220, 230, 255)
                pygame.draw.rect(s, cor, (x + TILE // 2 - 4, y + TILE // 2 - 5, 8, 7), 2)
                pygame.draw.circle(s, cor, (x + TILE // 2, y + TILE // 2 - 5), 3, 2)

        # coletáveis
        for col in a.coletaveis:
            x, y = int(col.x), int(col.y)
            osc = int(2 * math.sin(jogo.tempo * 0.12))
            if col.tipo == 'coracao':
                desenhar_coracao(s, x, y + osc, 18, (235, 50, 70))
            elif col.tipo == 'habilidade':
                pygame.draw.circle(s, (40, 70, 110), (x, y + osc), 11)
                desenhar_raio_icone(s, x, y + osc, (130, 220, 255))
            else:
                cor = (255, 215, 60) if col.tipo == 'chave_ceu' else (225, 235, 255)
                desenhar_chave(s, x, y + osc, cor)

        # raios de Zeus (telegrafados)
        for rz in a.raios:
            if rz.t > 0:
                raio = 26 + (rz.t % 10)
                pygame.draw.circle(s, (255, 230, 120), (int(rz.x), int(rz.y)), raio, 2)
            else:
                pygame.draw.line(s, (255, 255, 200), (int(rz.x), 0), (int(rz.x), int(rz.y)), 5)
                pygame.draw.circle(s, (255, 255, 220), (int(rz.x), int(rz.y)), 30, 4)

        # tiros
        for t in a.tiros:
            pygame.draw.circle(s, t.cor, (int(t.x), int(t.y)), t.raio)

        # inimigos
        for ini in a.inimigos:
            self.desenhar_inimigo(s, ini, jogo.tempo)

        # jogador
        j = jogo.jogador
        visivel = j.invuln == 0 or (j.invuln // 4) % 2 == 0
        if visivel:
            rect = j.rect()
            pygame.draw.rect(s, (70, 110, 230), rect)
            pygame.draw.rect(s, (25, 45, 120), rect, 2)
            ox, oy = rect.centerx + int(j.dir[0] * 4), rect.centery - 3 + int(j.dir[1] * 3)
            pygame.draw.circle(s, (255, 255, 255), (ox - 3, oy), 2)
            pygame.draw.circle(s, (255, 255, 255), (ox + 3, oy), 2)

        tela.fill((16, 14, 18))
        tela.blit(s, (0, HUD))
        self.desenhar_hud(tela, jogo)

        # barra de chefe
        for ini in a.inimigos:
            if ini.chefe():
                larg = 300
                x0 = LARG // 2 - larg // 2
                pygame.draw.rect(tela, (30, 30, 30), (x0, HUD + 8, larg, 14))
                vivo = int(larg * ini.hp / ini.hp_max)
                pygame.draw.rect(tela, (200, 40, 60), (x0, HUD + 8, vivo, 14))
                pygame.draw.rect(tela, (255, 255, 255), (x0, HUD + 8, larg, 14), 2)
                nome = self.f_peq.render(ini.nome, True, (255, 255, 255))
                tela.blit(nome, (LARG // 2 - nome.get_width() // 2, HUD + 24))

        # mensagens
        for i, (texto, t) in enumerate(self.msgs_visiveis(jogo)):
            img = self.f_med.render(texto, True, (255, 250, 220))
            fundo = pygame.Surface((img.get_width() + 16, img.get_height() + 6))
            fundo.set_alpha(min(170, t * 3))
            fundo.fill((0, 0, 0))
            x0 = LARG // 2 - img.get_width() // 2
            y0 = ALT - 70 - i * 30
            tela.blit(fundo, (x0 - 8, y0 - 3))
            tela.blit(img, (x0, y0))

        if jogo.estado == 'morto':
            self.tela_final(tela, 'VOCÊ MORREU', (220, 40, 40), 'Aperte R para tentar de novo')
        elif jogo.estado == 'vitoria':
            self.tela_final(tela, 'ZEUS FOI DERROTADO!', (255, 215, 60),
                            'Você conquistou a Torre dos Deuses — R para jogar de novo')

    def msgs_visiveis(self, jogo):
        return list(reversed(jogo.msgs[-3:]))

    def desenhar_inimigo(self, s, ini, tempo):
        x, y = int(ini.x), int(ini.y)
        cor = (255, 255, 255) if ini.flash > 0 else ini.cor
        pygame.draw.circle(s, cor, (x, y), ini.raio)
        pygame.draw.circle(s, (20, 10, 10), (x, y), ini.raio, 2)
        if ini.tipo == 'demonio':
            pygame.draw.polygon(s, (120, 20, 15), [(x - 8, y - 6), (x - 11, y - 15), (x - 3, y - 9)])
            pygame.draw.polygon(s, (120, 20, 15), [(x + 8, y - 6), (x + 11, y - 15), (x + 3, y - 9)])
            pygame.draw.circle(s, (255, 230, 60), (x - 4, y - 2), 2)
            pygame.draw.circle(s, (255, 230, 60), (x + 4, y - 2), 2)
        elif ini.tipo == 'anjo':
            pygame.draw.circle(s, (255, 220, 90), (x, y - ini.raio - 4), 6, 2)
            pygame.draw.circle(s, (60, 60, 90), (x - 4, y - 2), 2)
            pygame.draw.circle(s, (60, 60, 90), (x + 4, y - 2), 2)
        elif ini.tipo == 'hades':
            for k in (-8, 0, 8):
                pygame.draw.polygon(s, (140, 60, 200),
                                    [(x + k - 4, y - ini.raio + 2), (x + k, y - ini.raio - 9),
                                     (x + k + 4, y - ini.raio + 2)])
            pygame.draw.circle(s, (255, 80, 40), (x - 6, y - 3), 3)
            pygame.draw.circle(s, (255, 80, 40), (x + 6, y - 3), 3)
        elif ini.tipo == 'zeus':
            pygame.draw.circle(s, (255, 220, 80), (x, y), ini.raio + 4 + (tempo // 8) % 3, 2)
            desenhar_raio_icone(s, x, y + 2, (255, 200, 40))
            pygame.draw.circle(s, (80, 90, 120), (x - 5, y - 6), 2)
            pygame.draw.circle(s, (80, 90, 120), (x + 5, y - 6), 2)
        # barra de vida (inimigos comuns)
        if not ini.chefe() and ini.hp < ini.hp_max:
            w = ini.raio * 2
            pygame.draw.rect(s, (40, 40, 40), (x - ini.raio, y - ini.raio - 8, w, 4))
            pygame.draw.rect(s, (80, 220, 80),
                             (x - ini.raio, y - ini.raio - 8, int(w * ini.hp / ini.hp_max), 4))

    def desenhar_hud(self, tela, jogo):
        j = jogo.jogador
        pygame.draw.rect(tela, (24, 20, 26), (0, 0, LARG, HUD))
        pygame.draw.line(tela, (90, 80, 70), (0, HUD - 1), (LARG, HUD - 1), 2)
        # corações
        for i in range(j.vidas_max):
            cor = (235, 50, 70) if i < j.vidas else (70, 55, 60)
            desenhar_coracao(tela, 20 + i * 24, 16, 18, cor)
        # chaves
        x = 20
        for chave in ('chave_ceu', 'chave_olimpo'):
            if chave in j.chaves:
                cor = (255, 215, 60) if chave == 'chave_ceu' else (225, 235, 255)
                desenhar_chave(tela, x, 36, cor)
                x += 28
        # habilidades ganhas (canto direito do HUD)
        hx = LARG - 24
        for hab, tecla, cor in (('raio', 'X', (130, 220, 255)),
                                ('furia', 'Z', (255, 140, 50)),
                                ('investida', 'C', (140, 235, 140))):
            if hab not in j.habilidades:
                continue
            pygame.draw.rect(tela, (45, 40, 50), (hx - 11, 8, 22, 32), border_radius=4)
            if hab == 'raio':
                desenhar_raio_icone(tela, hx, 18, cor)
            elif hab == 'furia':
                pygame.draw.circle(tela, cor, (hx, 18), 6)
                pygame.draw.circle(tela, (255, 220, 120), (hx, 17), 3)
            else:
                pygame.draw.polygon(tela, cor, [(hx - 6, 14), (hx + 2, 18), (hx - 6, 22)])
                pygame.draw.polygon(tela, cor, [(hx - 1, 14), (hx + 7, 18), (hx - 1, 22)])
            letra = self.f_peq.render(tecla, True, (230, 230, 230))
            tela.blit(letra, (hx - letra.get_width() // 2, 26))
            hx -= 28
        # título do andar
        titulo = self.f_med.render(jogo.andar().titulo, True, (255, 240, 200))
        tela.blit(titulo, (LARG // 2 - titulo.get_width() // 2, 6))
        ajuda = self.f_peq.render(
            'Setas/WASD mover · ESPAÇO atirar · E porta · C investida · Z fúria · X raio',
            True, (170, 160, 150))
        tela.blit(ajuda, (LARG // 2 - ajuda.get_width() // 2, 28))

    def tela_final(self, tela, titulo, cor, sub):
        veu = pygame.Surface((LARG, ALT))
        veu.set_alpha(160)
        veu.fill((0, 0, 0))
        tela.blit(veu, (0, 0))
        t1 = self.f_grd.render(titulo, True, cor)
        t2 = self.f_med.render(sub, True, (240, 240, 240))
        tela.blit(t1, (LARG // 2 - t1.get_width() // 2, ALT // 2 - 60))
        tela.blit(t2, (LARG // 2 - t2.get_width() // 2, ALT // 2 + 4))


# ---------------------------------------------------------------- principal

def main():
    pygame.init()
    tela = pygame.display.set_mode((LARG, ALT))
    pygame.display.set_caption('A Torre dos Deuses')
    clock = pygame.time.Clock()
    rnd = Renderizador()
    jogo = Jogo()

    frames = 0
    tiles_teste = {'meio': (13, 5), 'inferno': (5, 5), 'submundo': (20, 20),
                   'ceu': (13, 5), 'olimpo': (20, 20)}
    ordem_teste = ['inferno', 'submundo', 'ceu', 'olimpo', 'meio']

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                return
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if ev.key == pygame.K_e:
                    jogo.abrir_porta()
                if ev.key in (pygame.K_c, pygame.K_LSHIFT):
                    jogo.investida()
                if ev.key == pygame.K_r and jogo.estado != 'jogando':
                    jogo = Jogo()

        jogo.atualizar(pygame.key.get_pressed())
        rnd.msgs = jogo.msgs
        rnd.desenhar(tela, jogo)
        pygame.display.flip()
        clock.tick(FPS)

        if MODO_TESTE:
            frames += 1
            if frames % 45 == 0:
                i = frames // 45 - 1
                if i < len(ordem_teste):
                    nome = ordem_teste[i]
                    jogo.mudar_andar(nome, tiles_teste[nome])
                else:
                    print('TESTE OK — %d frames, andar final: %s' % (frames, jogo.atual))
                    pygame.quit()
                    return


if __name__ == '__main__':
    main()