# -*- coding: utf-8 -*-
"""
MAGO: ENTRE O INFERNO E O CÉU
=============================
Jogo top-down 2D feito em pygame.

HISTÓRIA / PROGRESSÃO:
  1. Você nasce numa clareira com uma porta trancada à sua frente (Santuário)
     e uma trancada em cima (Céu). A descida para o INFERNO está aberta.
  2. Inferno - Andar 1: inimigos + upgrades (mais fácil)
  3. Inferno - Andar 2: BOSS Diabo -> dá a CHAVE DO CÉU
  4. Céu - Andar 1: inimigos + upgrades (dificuldade média)
  5. Céu - Andar 2: BOSS Zeus -> dá a CHAVE DO SANTUÁRIO
  6. Porta da frente do spawn: BOSS FINAL Mago Sombrio (sua cópia maligna) - difícil

CONTROLES:
  WASD / Setas ... mover
  Mouse .......... mirar
  Clique esq ..... atirar magia (pode segurar)
  ESPAÇO ......... dash (esquiva com invencibilidade)
  P / ESC ........ pausar
  R .............. reiniciar (no game over / vitória)

Requisitos:  pip install pygame
Rodar:       python mago_inferno_ceu.py
"""
import pygame
import math
import random
import sys

W, H = 960, 640
FPS = 60

ENTRADAS = {
    'top':    (W // 2, 88),
    'bottom': (W // 2, H - 88),
    'portal': (W // 2, H // 2 + 110),
}

CORES_TEMA = {
    'natureza': dict(chao=(64, 118, 68),  det=(56, 105, 60),  par=(40, 72, 44)),
    'inferno':  dict(chao=(46, 18, 16),   det=(58, 25, 20),   par=(24, 9, 9)),
    'ceu':      dict(chao=(206, 226, 244), det=(192, 214, 236), par=(150, 182, 218)),
    'final':    dict(chao=(33, 24, 46),   det=(42, 31, 58),   par=(17, 11, 27)),
}

PAL_JOGADOR = dict(manto=(124, 64, 204), corpo=(70, 40, 120), corpo2=(120, 70, 200),
                   chapeu=(50, 20, 90), cajado=(150, 100, 50), orbe=(120, 220, 255),
                   olhos=None)
PAL_SOMBRIO = dict(manto=(46, 14, 66), corpo=(24, 14, 38), corpo2=(58, 30, 84),
                   chapeu=(14, 6, 26), cajado=(70, 45, 45), orbe=(255, 70, 120),
                   olhos=(255, 50, 50))


def clamp(v, a, b):
    return max(a, min(b, v))


def seed_de(nome):
    return sum((i + 1) * ord(c) for i, c in enumerate(nome))


# ============================================================ PARTÍCULA
class Particula:
    def __init__(self, x, y, cor, vx=None, vy=None, vida=None, raio=None, grav=0.04):
        ang = random.uniform(0, math.tau)
        v = random.uniform(0.6, 3.2)
        self.x, self.y = x, y
        self.vx = vx if vx is not None else math.cos(ang) * v
        self.vy = vy if vy is not None else math.sin(ang) * v
        self.vida = vida if vida else random.randint(12, 26)
        self.vmax = self.vida
        self.raio = raio if raio else random.randint(2, 4)
        self.cor = cor
        self.grav = grav

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.grav
        self.vida -= 1

    def desenhar(self, s):
        if self.vida <= 0:
            return
        t = self.vida / self.vmax
        r = max(1, int(self.raio * t + 0.5))
        cor = tuple(int(c * (0.35 + 0.65 * t)) for c in self.cor)
        pygame.draw.circle(s, cor, (int(self.x), int(self.y)), r)


# ============================================================ PROJÉTIL
class Projetil:
    def __init__(self, x, y, vx, vy, amigo, dano=1.0, cor=(140, 220, 255), raio=5, vida=320):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.amigo = amigo
        self.dano = dano
        self.cor = cor
        self.raio = raio
        self.vida = vida
        self.viva = True

    def update(self, game):
        self.x += self.vx
        self.y += self.vy
        self.vida -= 1
        if game.frame % 3 == 0:
            game.particulas.append(
                Particula(self.x, self.y, self.cor, vx=0, vy=0, vida=8, raio=2, grav=0))
        if (self.vida <= 0 or self.x < 30 or self.x > W - 30
                or self.y < 30 or self.y > H - 30):
            self.viva = False

    def desenhar(self, s):
        x, y = int(self.x), int(self.y)
        pygame.draw.circle(s, tuple(c // 2 for c in self.cor), (x, y), self.raio + 3)
        pygame.draw.circle(s, self.cor, (x, y), self.raio)
        pygame.draw.circle(s, (255, 255, 255), (x, y), max(1, self.raio - 3))


# ============================================================ DESENHO DO MAGO (jogador e cópia maligna)
def desenhar_mago(s, x, y, ang, pal):
    # manto (atrás, oposto à direção)
    am = ang + math.pi
    pontos = []
    for a in (-0.8, 0.0, 0.8):
        pontos.append((x + math.cos(am + a) * 27, y + math.sin(am + a) * 27))
    pygame.draw.polygon(s, pal['manto'], pontos)
    # corpo
    pygame.draw.circle(s, pal['corpo'], (int(x), int(y)), 19)
    pygame.draw.circle(s, pal['corpo2'], (int(x), int(y)), 15)
    # olhos (versão maligna)
    if pal['olhos']:
        ox = math.cos(ang) * 6
        oy = math.sin(ang) * 6
        px = -math.sin(ang) * 5
        py = math.cos(ang) * 5
        pygame.draw.circle(s, pal['olhos'], (int(x + ox + px), int(y + oy + py)), 3)
        pygame.draw.circle(s, pal['olhos'], (int(x + ox - px), int(y + oy - py)), 3)
    # chapéu
    base = ang - math.pi / 2
    ponta = (x + math.cos(base) * 27, y + math.sin(base) * 27)
    bl = (x + math.cos(base + 0.8) * 17, y + math.sin(base + 0.8) * 17)
    br = (x + math.cos(base - 0.8) * 17, y + math.sin(base - 0.8) * 17)
    pygame.draw.polygon(s, pal['chapeu'], [bl, br, ponta])
    # cajado
    fx = x + math.cos(ang) * 33
    fy = y + math.sin(ang) * 33
    pygame.draw.line(s, pal['cajado'], (int(x), int(y)), (int(fx), int(fy)), 4)
    pygame.draw.circle(s, pal['orbe'], (int(fx), int(fy)), 6)
    pygame.draw.circle(s, (255, 255, 255), (int(fx), int(fy)), 3)


# ============================================================ JOGADOR
class Jogador:
    def __init__(self):
        self.x, self.y = W / 2, H / 2 + 160
        self.raio = 15
        self.vel = 4.2
        self.max_coracoes = 5
        self.coracoes = 5
        self.dano = 1.0
        self.cadencia = 16
        self.proj_vel = 8.0
        self.cd = 0
        self.invuln = 0
        self.ang = -math.pi / 2
        self.dash_cd = 0
        self.dash_t = 0
        self.ddx, self.ddy = 0, -1

    def update(self, game, teclas, mx, my, atirando):
        dx = (teclas[pygame.K_d] or teclas[pygame.K_RIGHT]) - (teclas[pygame.K_a] or teclas[pygame.K_LEFT])
        dy = (teclas[pygame.K_s] or teclas[pygame.K_DOWN]) - (teclas[pygame.K_w] or teclas[pygame.K_UP])
        if dx or dy:
            n = math.hypot(dx, dy)
            dx, dy = dx / n, dy / n
            self.ddx, self.ddy = dx, dy

        # dash
        if teclas[pygame.K_SPACE] and self.dash_cd <= 0 and self.dash_t <= 0:
            self.dash_t = 10
            self.dash_cd = 55
            self.invuln = max(self.invuln, 14)
        if self.dash_t > 0:
            self.x += self.ddx * self.vel * 3.1
            self.y += self.ddy * self.vel * 3.1
            self.dash_t -= 1
            game.particulas.append(Particula(self.x, self.y, PAL_JOGADOR['manto'],
                                             vx=0, vy=0, vida=12, raio=5, grav=0))
        else:
            self.x += dx * self.vel
            self.y += dy * self.vel

        self.x = clamp(self.x, 42, W - 42)
        self.y = clamp(self.y, 42, H - 42)

        self.ang = math.atan2(my - self.y, mx - self.x)

        if self.cd > 0:
            self.cd -= 1
        if self.invuln > 0:
            self.invuln -= 1
        if self.dash_cd > 0:
            self.dash_cd -= 1

        if atirando and self.cd <= 0:
            self.atirar(game, mx, my)

    def atirar(self, game, tx, ty):
        if self.cd > 0:
            return
        ang = math.atan2(ty - self.y, tx - self.x)
        fx = self.x + math.cos(ang) * 33
        fy = self.y + math.sin(ang) * 33
        game.projeteis.append(Projetil(fx, fy, math.cos(ang) * self.proj_vel,
                                       math.sin(ang) * self.proj_vel,
                                       amigo=True, dano=self.dano,
                                       cor=(130, 220, 255), raio=5))
        for _ in range(3):
            game.particulas.append(Particula(fx, fy, (170, 230, 255), vida=10, raio=2, grav=0))
        self.cd = self.cadencia

    def levar_dano(self, game, n=1):
        if self.invuln > 0 or self.dash_t > 0:
            return False
        self.coracoes -= n
        self.invuln = 70
        game.shake = 11
        for _ in range(16):
            game.particulas.append(Particula(self.x, self.y, (235, 70, 90)))
        return True

    def desenhar(self, s):
        if self.invuln > 0 and (self.invuln // 4) % 2 == 0:
            return
        desenhar_mago(s, self.x, self.y, self.ang, PAL_JOGADOR)


# ============================================================ INIMIGOS
STATS_INIMIGO = {
    # inferno (fácil)
    'diabinho': dict(hp=3, raio=14, vel=1.6, cd=110, pvel=3.0,
                     cor=(210, 70, 60), pcor=(255, 140, 60)),
    'cuspidor': dict(hp=4, raio=17, vel=0.0, cd=145, pvel=2.8,
                     cor=(82, 52, 48), pcor=(255, 110, 40)),
    # céu (médio)
    'querubim': dict(hp=5, raio=14, vel=2.1, cd=80, pvel=4.3,
                     cor=(245, 245, 252), pcor=(255, 210, 80)),
    'serafim':  dict(hp=6, raio=16, vel=1.2, cd=135, pvel=4.6,
                     cor=(248, 212, 110), pcor=(255, 230, 110)),
}


class Inimigo:
    def __init__(self, kind, x, y):
        st = STATS_INIMIGO[kind]
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.hp = st['hp']
        self.hpmax = st['hp']
        self.raio = st['raio']
        self.vel = st['vel']
        self.cd = st['cd']
        self.timer = random.randint(40, st['cd'])
        self.pvel = st['pvel']
        self.cor = st['cor']
        self.pcor = st['pcor']
        self.flash = 0
        self.rajada = 0
        self.raj_t = 0
        self.orb_dir = random.choice((-1, 1))
        self.orb_flip = random.randint(90, 200)

    def _atira(self, game, j, ang_off=0.0, vel=None):
        v = vel or self.pvel
        ang = math.atan2(j.y - self.y, j.x - self.x) + ang_off
        game.projeteis.append(Projetil(self.x, self.y, math.cos(ang) * v, math.sin(ang) * v,
                                       amigo=False, cor=self.pcor, raio=6))

    def update(self, game):
        j = game.jogador
        d = math.hypot(j.x - self.x, j.y - self.y) or 1
        nx, ny = (j.x - self.x) / d, (j.y - self.y) / d

        if self.kind == 'diabinho':
            if d > 200:
                self.x += nx * self.vel
                self.y += ny * self.vel
            else:
                self.x += -ny * self.vel * 0.6 * self.orb_dir
                self.y += nx * self.vel * 0.6 * self.orb_dir
        elif self.kind == 'querubim':
            self.x += nx * (d - 250) * 0.018 + (-ny) * self.vel * self.orb_dir
            self.y += ny * (d - 250) * 0.018 + (nx) * self.vel * self.orb_dir
            self.orb_flip -= 1
            if self.orb_flip <= 0:
                self.orb_dir *= -1
                self.orb_flip = random.randint(90, 200)
        elif self.kind == 'serafim':
            if d > 300:
                self.x += nx * self.vel
                self.y += ny * self.vel

        self.x = clamp(self.x, 60, W - 60)
        self.y = clamp(self.y, 100, H - 70)

        # tiro
        if self.kind == 'serafim':
            if self.rajada > 0:
                self.raj_t -= 1
                if self.raj_t <= 0:
                    self._atira(game, j)
                    self.rajada -= 1
                    self.raj_t = 9
            else:
                self.timer -= 1
                if self.timer <= 0:
                    self.rajada = 3
                    self.raj_t = 1
                    self.timer = self.cd
        else:
            self.timer -= 1
            if self.timer <= 0:
                if self.kind == 'cuspidor':
                    for off in (-0.3, 0.0, 0.3):
                        self._atira(game, j, off)
                else:
                    self._atira(game, j)
                self.timer = self.cd

        if self.flash > 0:
            self.flash -= 1

    def levar_dano(self, game, dano):
        self.hp -= dano
        self.flash = 6
        for _ in range(5):
            game.particulas.append(Particula(self.x, self.y, self.pcor))
        return self.hp <= 0

    def desenhar(self, s):
        x, y = int(self.x), int(self.y)
        cor = (255, 255, 255) if self.flash > 0 else self.cor
        pygame.draw.circle(s, (0, 0, 0), (x + 3, y + 4), self.raio)  # sombra

        if self.kind == 'diabinho':
            pygame.draw.circle(s, cor, (x, y), self.raio)
            pygame.draw.polygon(s, (120, 25, 25), [(x - 12, y - 8), (x - 4, y - 10), (x - 14, y - 20)])
            pygame.draw.polygon(s, (120, 25, 25), [(x + 12, y - 8), (x + 4, y - 10), (x + 14, y - 20)])
            pygame.draw.circle(s, (255, 230, 80), (x - 5, y - 3), 3)
            pygame.draw.circle(s, (255, 230, 80), (x + 5, y - 3), 3)
        elif self.kind == 'cuspidor':
            pygame.draw.circle(s, cor, (x, y), self.raio)
            pygame.draw.circle(s, (40, 22, 20), (x, y), self.raio, 3)
            pygame.draw.circle(s, (255, 120, 40), (x, y + 3), 7)
            pygame.draw.circle(s, (255, 200, 80), (x, y + 3), 3)
            pygame.draw.line(s, (40, 22, 20), (x - 10, y - 8), (x - 3, y - 4), 2)
            pygame.draw.line(s, (40, 22, 20), (x + 10, y - 9), (x + 2, y - 5), 2)
        elif self.kind == 'querubim':
            pygame.draw.ellipse(s, (255, 255, 255), (x - self.raio - 9, y - 7, 12, 16))
            pygame.draw.ellipse(s, (255, 255, 255), (x + self.raio - 3, y - 7, 12, 16))
            pygame.draw.circle(s, cor, (x, y), self.raio)
            pygame.draw.circle(s, (255, 220, 90), (x, y - self.raio - 5), 7, 2)  # auréola
            pygame.draw.circle(s, (90, 90, 120), (x - 5, y - 2), 2)
            pygame.draw.circle(s, (90, 90, 120), (x + 5, y - 2), 2)
        elif self.kind == 'serafim':
            pygame.draw.circle(s, (255, 240, 170), (x, y), self.raio + 5, 2)
            pygame.draw.circle(s, cor, (x, y), self.raio)
            pygame.draw.circle(s, (255, 255, 255), (x, y), 8)
            pygame.draw.circle(s, (60, 60, 110), (x, y), 4)

        # vida
        if self.hp < self.hpmax:
            w = self.raio * 2
            f = self.hp / self.hpmax
            pygame.draw.rect(s, (40, 40, 40), (x - w // 2, y - self.raio - 12, w, 4))
            pygame.draw.rect(s, (90, 220, 90), (x - w // 2, y - self.raio - 12, int(w * f), 4))


# ============================================================ BOSSES
class Boss:
    DADOS = {
        'diabo':   dict(hp=60,  raio=40, nome='DIABO — Senhor do Inferno', cd=95,
                        pcor=(255, 120, 50)),
        'zeus':    dict(hp=100, raio=36, nome='ZEUS — Rei do Olimpo', cd=80,
                        pcor=(255, 235, 110)),
        'sombrio': dict(hp=150, raio=20, nome='MAGO SOMBRIO — Seu Reflexo', cd=70,
                        pcor=(255, 80, 200)),
    }
    SEQ = {
        'diabo':   ['anel', 'triplo'],
        'zeus':    ['rajada', 'raio', 'anel'],
        'sombrio': ['leque', 'espiral', 'tele'],
    }

    def __init__(self, kind):
        d = Boss.DADOS[kind]
        self.kind = kind
        self.x, self.y = W / 2, 200.0
        self.hp = d['hp']
        self.hpmax = d['hp']
        self.raio = d['raio']
        self.nome = d['nome']
        self.cd_base = d['cd']
        self.pcor = d['pcor']
        self.timer = 70
        self.idx = 0
        self.fase2 = False
        self.flash = 0
        self.ang_vis = math.pi / 2
        # estados de rajadas
        self.tri = 0
        self.tri_t = 0
        self.raj = 0
        self.raj_t = 0
        self.esp = 0
        self.esp_t = 0
        self.esp_ang = 0.0
        self.perp_dir = 1
        self.perp_t = 120

    # ---------- helpers de tiro ----------
    def _tiro(self, game, ang, vel, raio=7):
        game.projeteis.append(Projetil(self.x, self.y, math.cos(ang) * vel,
                                       math.sin(ang) * vel, amigo=False,
                                       cor=self.pcor, raio=raio))

    def _mirado(self, game, j, off=0.0, vel=4.0, raio=7):
        ang = math.atan2(j.y - self.y, j.x - self.x) + off
        self._tiro(game, ang, vel, raio)

    def _anel(self, game, n, vel, off=0.0):
        for i in range(n):
            self._tiro(game, off + i * math.tau / n, vel)
        for _ in range(14):
            game.particulas.append(Particula(self.x, self.y, self.pcor))

    # ---------- update ----------
    def update(self, game):
        j = game.jogador
        d = math.hypot(j.x - self.x, j.y - self.y) or 1
        nx, ny = (j.x - self.x) / d, (j.y - self.y) / d
        self.ang_vis = math.atan2(j.y - self.y, j.x - self.x)

        if self.flash > 0:
            self.flash -= 1

        # fase 2
        if not self.fase2 and self.hp <= self.hpmax * 0.5:
            self.fase2 = True
            game.msg('O chefe está furioso!', 110)
            game.shake = 12
            self._anel(game, 18 if self.kind != 'diabo' else 14, 3.4)

        # movimento
        if self.kind == 'diabo':
            if d > 180:
                self.x += nx * 1.25
                self.y += ny * 1.25
            else:
                self.x += -ny * 0.9 * self.perp_dir
                self.y += nx * 0.9 * self.perp_dir
        elif self.kind == 'zeus':
            self.x += nx * (d - 260) * 0.014 + (-ny) * 1.5 * self.perp_dir
            self.y += ny * (d - 260) * 0.014 + (nx) * 1.5 * self.perp_dir
        elif self.kind == 'sombrio':
            self.x += nx * (d - 235) * 0.02 + (-ny) * 1.7 * self.perp_dir
            self.y += ny * (d - 235) * 0.02 + (nx) * 1.7 * self.perp_dir
        self.perp_t -= 1
        if self.perp_t <= 0:
            self.perp_dir *= -1
            self.perp_t = random.randint(90, 180)
        self.x = clamp(self.x, 80, W - 80)
        self.y = clamp(self.y, 115, H - 95)

        # partículas ambiente
        if game.frame % 5 == 0:
            game.particulas.append(Particula(self.x + random.uniform(-self.raio, self.raio),
                                             self.y + random.uniform(-self.raio, self.raio),
                                             self.pcor, vida=14, raio=3, grav=-0.03))

        mult = 0.68 if self.fase2 else 1.0

        # rajadas em andamento
        if self.tri > 0:
            self.tri_t -= 1
            if self.tri_t <= 0:
                n = 5 if self.fase2 else 3
                spread = 0.26
                for k in range(n):
                    off = (k - (n - 1) / 2) * spread
                    self._mirado(game, j, off, vel=3.6)
                self.tri -= 1
                self.tri_t = 16
            return
        if self.raj > 0:
            self.raj_t -= 1
            if self.raj_t <= 0:
                self._mirado(game, j, random.uniform(-0.05, 0.05), vel=5.4, raio=6)
                self.raj -= 1
                self.raj_t = 8
            return
        if self.esp > 0:
            self.esp_t -= 1
            if self.esp_t <= 0:
                bracos = 4 if self.fase2 else 3
                for b in range(bracos):
                    self._tiro(game, self.esp_ang + b * math.tau / bracos, 3.3)
                self.esp_ang += 0.31
                self.esp -= 1
                self.esp_t = 4
            return

        # próximo padrão
        self.timer -= 1
        if self.timer > 0:
            return
        seq = Boss.SEQ[self.kind]
        padrao = seq[self.idx % len(seq)]
        self.idx += 1
        self.timer = int(self.cd_base * mult)

        if padrao == 'anel':
            n = (16 if self.fase2 else 12) if self.kind == 'diabo' else (18 if self.fase2 else 14)
            self._anel(game, n, 3.4, off=random.uniform(0, 0.5))
        elif padrao == 'triplo':
            self.tri = 3
            self.tri_t = 1
        elif padrao == 'rajada':
            self.raj = 6 if self.fase2 else 4
            self.raj_t = 1
        elif padrao == 'raio':
            game.telegrafos.append(dict(x=j.x, y=j.y, r=80, t=46, tmax=46, cor=self.pcor))
            if self.fase2:
                ang = random.uniform(0, math.tau)
                game.telegrafos.append(dict(x=clamp(j.x + math.cos(ang) * 130, 80, W - 80),
                                            y=clamp(j.y + math.sin(ang) * 130, 110, H - 80),
                                            r=80, t=58, tmax=58, cor=self.pcor))
        elif padrao == 'leque':
            n = 7 if self.fase2 else 5
            for k in range(n):
                off = (k - (n - 1) / 2) * 0.22
                self._mirado(game, j, off, vel=5.2, raio=6)
        elif padrao == 'espiral':
            self.esp = 20 if self.fase2 else 14
            self.esp_t = 1
            self.esp_ang = random.uniform(0, math.tau)
        elif padrao == 'tele':
            for _ in range(18):
                game.particulas.append(Particula(self.x, self.y, (160, 60, 200)))
            ang = random.uniform(0, math.tau)
            self.x = clamp(j.x + math.cos(ang) * 210, 90, W - 90)
            self.y = clamp(j.y + math.sin(ang) * 210, 120, H - 95)
            for _ in range(18):
                game.particulas.append(Particula(self.x, self.y, (255, 80, 200)))
            self._anel(game, 16 if self.fase2 else 12, 4.0)

    def levar_dano(self, game, dano):
        self.hp -= dano
        self.flash = 5
        for _ in range(4):
            game.particulas.append(Particula(self.x, self.y, self.pcor, vida=12))

    # ---------- desenho ----------
    def desenhar(self, s, frame):
        x, y = int(self.x), int(self.y)
        flash = self.flash > 0
        pygame.draw.circle(s, (0, 0, 0), (x + 4, y + 6), self.raio)  # sombra

        if self.kind == 'diabo':
            cor = (255, 255, 255) if flash else (190, 40, 35)
            pygame.draw.circle(s, cor, (x, y), self.raio)
            pygame.draw.circle(s, (235, 80, 60) if not flash else cor, (x, y), self.raio - 9)
            pygame.draw.polygon(s, (110, 18, 18),
                                [(x - 30, y - 18), (x - 12, y - 26), (x - 38, y - 52)])
            pygame.draw.polygon(s, (110, 18, 18),
                                [(x + 30, y - 18), (x + 12, y - 26), (x + 38, y - 52)])
            pygame.draw.circle(s, (255, 230, 60), (x - 13, y - 8), 6)
            pygame.draw.circle(s, (255, 230, 60), (x + 13, y - 8), 6)
            pygame.draw.circle(s, (0, 0, 0), (x - 13, y - 8), 3)
            pygame.draw.circle(s, (0, 0, 0), (x + 13, y - 8), 3)
            pygame.draw.arc(s, (90, 10, 10), (x - 16, y + 8, 32, 18), 0, math.pi, 3)
        elif self.kind == 'zeus':
            cor = (255, 255, 255) if flash else (235, 238, 248)
            pygame.draw.circle(s, cor, (x, y), self.raio)
            pygame.draw.polygon(s, (250, 250, 255),
                                [(x - 22, y + 4), (x + 22, y + 4), (x + 12, y + 36),
                                 (x, y + 28), (x - 12, y + 36)])  # barba
            zz = [(x - 24, y - self.raio + 2), (x - 14, y - self.raio - 12),
                  (x - 6, y - self.raio + 2), (x + 4, y - self.raio - 14),
                  (x + 12, y - self.raio + 2), (x + 22, y - self.raio - 10),
                  (x + 26, y - self.raio + 4)]
            pygame.draw.lines(s, (255, 215, 70), False, zz, 4)  # coroa de raios
            pygame.draw.circle(s, (90, 180, 255), (x - 12, y - 6), 5)
            pygame.draw.circle(s, (90, 180, 255), (x + 12, y - 6), 5)
        elif self.kind == 'sombrio':
            desenhar_mago(s, self.x, self.y, self.ang_vis, PAL_SOMBRIO)
            pygame.draw.circle(s, (120, 20, 60), (x, y), self.raio + 10, 2)


# ============================================================ PICKUPS
INFO_PICKUP = {
    'coracao':     dict(cor=(235, 70, 90),   letra='+',  nome='Coração recuperado!'),
    'dano':        dict(cor=(255, 110, 80),  letra='D',  nome='Cajado Afiado  (+0.5 de dano)'),
    'cadencia':    dict(cor=(120, 220, 255), letra='C',  nome='Conjuração Rápida  (atira mais rápido)'),
    'velocidade':  dict(cor=(140, 255, 140), letra='V',  nome='Botas Velozes  (+ velocidade)'),
    'coracao_max': dict(cor=(255, 120, 160), letra='♥',  nome='Coração Extra  (+1 coração máximo)'),
    'proj_vel':    dict(cor=(220, 180, 255), letra='M',  nome='Magia Veloz  (projétil mais rápido)'),
    'portal':      dict(cor=(255, 215, 80),  letra='O',  nome='Portal para a Clareira'),
}
POOL_UPGRADES = ['dano', 'cadencia', 'velocidade', 'coracao_max', 'proj_vel']


class Pickup:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.x, self.y = x, y
        self.t = random.uniform(0, math.tau)

    def aplicar(self, game):
        j = game.jogador
        k = self.kind
        if k == 'coracao':
            if j.coracoes >= j.max_coracoes:
                return False
            j.coracoes = min(j.max_coracoes, j.coracoes + 1)
        elif k == 'dano':
            j.dano += 0.5
        elif k == 'cadencia':
            j.cadencia = max(8, j.cadencia - 3)
        elif k == 'velocidade':
            j.vel += 0.7
        elif k == 'coracao_max':
            j.max_coracoes += 1
            j.coracoes += 1
        elif k == 'proj_vel':
            j.proj_vel += 1.3
        elif k == 'portal':
            game.mudar_sala('spawn', 'portal')
            return True
        if k != 'coracao' and k != 'portal':
            game.upgrades_pegos += 1
        game.msg(INFO_PICKUP[k]['nome'], 130)
        for _ in range(12):
            game.particulas.append(Particula(self.x, self.y, INFO_PICKUP[k]['cor']))
        return True

    def desenhar(self, s, fonte, jogador, frame):
        ofy = math.sin(frame * 0.08 + self.t) * 5
        x, y = int(self.x), int(self.y + ofy)
        info = INFO_PICKUP[self.kind]
        if self.kind == 'portal':
            r = 22 + int(math.sin(frame * 0.15) * 3)
            pygame.draw.circle(s, (255, 230, 140), (x, y), r, 3)
            pygame.draw.circle(s, (255, 200, 80), (x, y), r - 8, 2)
            pygame.draw.circle(s, (255, 255, 220), (x, y), 5)
        else:
            pygame.draw.circle(s, tuple(c // 2 for c in info['cor']), (x, y), 16)
            pygame.draw.circle(s, info['cor'], (x, y), 12)
            txt = fonte.render(info['letra'], True, (255, 255, 255))
            s.blit(txt, (x - txt.get_width() // 2, y - txt.get_height() // 2))
        if math.hypot(jogador.x - self.x, jogador.y - self.y) < 90:
            rot = fonte.render(info['nome'], True, (255, 255, 255))
            fundo = pygame.Rect(0, 0, rot.get_width() + 10, rot.get_height() + 4)
            fundo.center = (x, y - 30)
            pygame.draw.rect(s, (15, 15, 25), fundo, border_radius=5)
            s.blit(rot, (fundo.x + 5, fundo.y + 2))


# ============================================================ PORTAS E SALAS
class Porta:
    def __init__(self, lado, destino, entrada, bloqueio=None, rotulo=''):
        self.lado = lado
        self.destino = destino
        self.entrada = entrada
        self.bloqueio = bloqueio
        self.rotulo = rotulo
        self.aviso_cd = 0
        if lado == 'top':
            self.rect = pygame.Rect(W // 2 - 65, 0, 130, 46)
        elif lado == 'bottom':
            self.rect = pygame.Rect(W // 2 - 65, H - 46, 130, 46)
        else:  # centro (porta do santuário)
            self.rect = pygame.Rect(W // 2 - 52, H // 2 - 170, 104, 135)

    def motivo_tranca(self, game):
        return self.bloqueio(game) if self.bloqueio else None


class Sala:
    def __init__(self, nome, titulo, tema, portas, inimigos=(), boss=None):
        self.nome = nome
        self.titulo = titulo
        self.tema = tema
        self.portas = portas
        self.inimigos_tpl = list(inimigos)
        self.boss_kind = boss
        self.pickups = []
        self.limpa = len(self.inimigos_tpl) == 0
        self.boss_morto = False
        self.upgrades_ok = False
        self.deco = self._gerar_deco()

    def _gerar_deco(self):
        rng = random.Random(seed_de(self.nome))
        deco = []
        evitar_centro = (self.nome == 'spawn')

        def pos():
            for _ in range(40):
                x = rng.randint(95, W - 95)
                y = rng.randint(115, H - 130)
                if evitar_centro and abs(x - W / 2) < 140 and H / 2 - 200 < y < H / 2 + 40:
                    continue
                if abs(x - W / 2) < 90 and (y < 150 or y > H - 160):
                    continue
                return x, y
            return rng.randint(95, W - 95), rng.randint(115, H - 130)

        if self.tema == 'natureza':
            for _ in range(9):
                deco.append(('arvore', *pos(), rng.randint(14, 22)))
            for _ in range(14):
                deco.append(('flor', *pos(), rng.choice([(255, 120, 150), (255, 220, 90), (180, 140, 255)])))
            for _ in range(22):
                deco.append(('grama', *pos(), 0))
        elif self.tema == 'inferno':
            for _ in range(6):
                deco.append(('lava', *pos(), rng.randint(22, 42)))
            for _ in range(8):
                deco.append(('pedra', *pos(), rng.randint(8, 15)))
            for _ in range(7):
                deco.append(('osso', *pos(), rng.uniform(0, math.pi)))
        elif self.tema == 'ceu':
            for _ in range(7):
                deco.append(('nuvem', *pos(), rng.randint(18, 32)))
            for _ in range(4):
                deco.append(('pilar', *pos(), 0))
            for _ in range(16):
                deco.append(('brilho', *pos(), rng.uniform(0, math.tau)))
        elif self.tema == 'final':
            for _ in range(8):
                deco.append(('runa', *pos(), rng.uniform(0, math.tau)))
            for _ in range(6):
                deco.append(('tocha', *pos(), rng.uniform(0, math.tau)))
        return deco


# ============================================================ GAME
class Game:
    def __init__(self):
        if not pygame.get_init():
            pygame.init()
        self.canvas = pygame.Surface((W, H))
        self.f16 = pygame.font.SysFont('consolas', 16, bold=True)
        self.f20 = pygame.font.SysFont('consolas', 20, bold=True)
        self.f28 = pygame.font.SysFont('consolas', 28, bold=True)
        self.f44 = pygame.font.SysFont('consolas', 44, bold=True)

        self.jogador = Jogador()
        self.salas = self._construir_salas()
        self.sala = self.salas['spawn']
        self.inimigos = []
        self.projeteis = []
        self.particulas = []
        self.telegrafos = []
        self.boss = None
        self.msgs = []
        self.frame = 0
        self.shake = 0
        self.fade = 25
        self.porta_cd = 0
        self.chave_ceu = False
        self.chave_final = False
        self.estado = 'jogando'   # jogando | pausa | gameover | vitoria
        self.reiniciar = False
        self.upgrades_pegos = 0
        self.vitoria_timer = -1
        self.msg('Desça as escadas ao sul... o Inferno te espera.', 240)

    # ---------------- salas ----------------
    def _construir_salas(self):
        s = {}
        s['spawn'] = Sala('spawn', 'Clareira do Início', 'natureza', [
            Porta('bottom', 'inferno1', 'top', None, 'Descida ao Inferno'),
            Porta('top', 'ceu1', 'bottom',
                  lambda g: None if g.chave_ceu else 'Trancada — precisa da Chave do Céu',
                  'Portão do Céu'),
            Porta('centro', 'final', 'bottom',
                  lambda g: None if g.chave_final else 'Trancada — precisa da Chave do Santuário',
                  'Porta do Santuário'),
        ])
        s['inferno1'] = Sala('inferno1', 'Inferno — Andar 1', 'inferno', [
            Porta('top', 'spawn', 'bottom', None, 'Voltar à Clareira'),
            Porta('bottom', 'inferno2', 'top',
                  lambda g: None if g.salas['inferno1'].limpa else 'Derrote todos os inimigos!',
                  'Covil do Diabo'),
        ], inimigos=[('diabinho', 300, 400), ('diabinho', 660, 400),
                     ('diabinho', 480, 300), ('cuspidor', 480, 505)])
        s['inferno2'] = Sala('inferno2', 'Inferno — Covil do Diabo', 'inferno', [
            Porta('top', 'inferno1', 'bottom',
                  lambda g: None if g.salas['inferno2'].boss_morto else 'O Diabo selou a porta!',
                  'Subir'),
        ], boss='diabo')
        s['ceu1'] = Sala('ceu1', 'Céu — Andar 1', 'ceu', [
            Porta('bottom', 'spawn', 'top', None, 'Voltar à Clareira'),
            Porta('top', 'ceu2', 'bottom',
                  lambda g: None if g.salas['ceu1'].limpa else 'Derrote todos os inimigos!',
                  'Salão de Zeus'),
        ], inimigos=[('querubim', 300, 240), ('querubim', 660, 240),
                     ('querubim', 480, 180), ('serafim', 250, 360), ('serafim', 710, 360)])
        s['ceu2'] = Sala('ceu2', 'Céu — Salão de Zeus', 'ceu', [
            Porta('bottom', 'ceu1', 'top',
                  lambda g: None if g.salas['ceu2'].boss_morto else 'Zeus selou a porta!',
                  'Descer'),
        ], boss='zeus')
        s['final'] = Sala('final', 'Santuário Sombrio', 'final', [
            Porta('bottom', 'spawn', 'portal',
                  lambda g: None if g.salas['final'].boss_morto else 'O Mago Sombrio selou a porta!',
                  'Sair'),
        ], boss='sombrio')
        return s

    def mudar_sala(self, nome, entrada):
        self.sala = self.salas[nome]
        self.projeteis.clear()
        self.particulas.clear()
        self.telegrafos.clear()
        self.jogador.x, self.jogador.y = ENTRADAS[entrada]
        self.porta_cd = 25
        self.fade = 18
        self.inimigos = []
        if not self.sala.limpa:
            self.inimigos = [Inimigo(k, x, y) for k, x, y in self.sala.inimigos_tpl]
        self.boss = None
        if self.sala.boss_kind and not self.sala.boss_morto:
            self.boss = Boss(self.sala.boss_kind)
            self.msg(self.boss.nome, 170, grande=True)

    # ---------------- mensagens ----------------
    def msg(self, txt, t=120, grande=False):
        self.msgs.append(dict(txt=txt, t=t, tmax=t, grande=grande))

    # ---------------- eventos ----------------
    def evento(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_p, pygame.K_ESCAPE) and self.estado in ('jogando', 'pausa'):
                self.estado = 'pausa' if self.estado == 'jogando' else 'jogando'
            if e.key == pygame.K_r and self.estado in ('gameover', 'vitoria'):
                self.reiniciar = True

    # ---------------- update ----------------
    def update(self):
        if self.estado != 'jogando':
            return
        self.frame += 1
        if self.shake > 0:
            self.shake -= 1
        if self.fade > 0:
            self.fade -= 1
        if self.porta_cd > 0:
            self.porta_cd -= 1

        teclas = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()
        atirando = pygame.mouse.get_pressed()[0]
        j = self.jogador
        j.update(self, teclas, mx, my, atirando)

        # ---- portas ----
        prect = pygame.Rect(int(j.x - j.raio), int(j.y - j.raio), j.raio * 2, j.raio * 2)
        for porta in self.sala.portas:
            if porta.aviso_cd > 0:
                porta.aviso_cd -= 1
            if not prect.colliderect(porta.rect):
                continue
            motivo = porta.motivo_tranca(self)
            if motivo is None:
                if self.porta_cd <= 0:
                    self.mudar_sala(porta.destino, porta.entrada)
                    return
            else:
                # porta central é sólida: empurra o jogador para fora
                if porta.lado == 'centro':
                    dxl = porta.rect.right - prect.left
                    dxr = prect.right - porta.rect.left
                    dyt = porta.rect.bottom - prect.top
                    dyb = prect.bottom - porta.rect.top
                    m = min(dxl, dxr, dyt, dyb)
                    if m == dxl:
                        j.x += dxl
                    elif m == dxr:
                        j.x -= dxr
                    elif m == dyt:
                        j.y += dyt
                    else:
                        j.y -= dyb
                if porta.aviso_cd <= 0:
                    self.msg(motivo, 90)
                    porta.aviso_cd = 95
            if porta.lado != 'centro' and motivo is not None:
                # empurra de volta nas portas de borda trancadas
                if porta.lado == 'top':
                    j.y = max(j.y, porta.rect.bottom + j.raio)
                else:
                    j.y = min(j.y, porta.rect.top - j.raio)

        # ---- inimigos ----
        for ini in self.inimigos:
            ini.update(self)
            if math.hypot(ini.x - j.x, ini.y - j.y) < ini.raio + j.raio:
                j.levar_dano(self)

        # ---- boss ----
        if self.boss:
            self.boss.update(self)
            if math.hypot(self.boss.x - j.x, self.boss.y - j.y) < self.boss.raio + j.raio:
                j.levar_dano(self)
            if self.boss.hp <= 0:
                self._boss_derrotado()

        # ---- projéteis ----
        for p in self.projeteis:
            p.update(self)
            if not p.viva:
                continue
            if p.amigo:
                alvo_morto = False
                for ini in self.inimigos:
                    if math.hypot(p.x - ini.x, p.y - ini.y) < p.raio + ini.raio:
                        p.viva = False
                        if ini.levar_dano(self, p.dano):
                            self._inimigo_morto(ini)
                        alvo_morto = True
                        break
                if not alvo_morto and self.boss:
                    b = self.boss
                    if math.hypot(p.x - b.x, p.y - b.y) < p.raio + b.raio:
                        p.viva = False
                        b.levar_dano(self, p.dano)
            else:
                if math.hypot(p.x - j.x, p.y - j.y) < p.raio + j.raio:
                    if j.levar_dano(self):
                        p.viva = False
        self.projeteis = [p for p in self.projeteis if p.viva]

        # ---- telégrafos (raio do céu) ----
        for tg in self.telegrafos:
            tg['t'] -= 1
            if tg['t'] <= 0:
                if math.hypot(tg['x'] - j.x, tg['y'] - j.y) < tg['r']:
                    j.levar_dano(self)
                for _ in range(22):
                    self.particulas.append(Particula(tg['x'], tg['y'], tg['cor']))
                for i in range(6):
                    ang = i * math.tau / 6
                    self.projeteis.append(Projetil(tg['x'], tg['y'],
                                                   math.cos(ang) * 2.4, math.sin(ang) * 2.4,
                                                   amigo=False, cor=tg['cor'], raio=5, vida=90))
                self.shake = max(self.shake, 8)
        self.telegrafos = [t for t in self.telegrafos if t['t'] > 0]

        # ---- limpeza do andar -> upgrades ----
        if (not self.sala.limpa and self.sala.inimigos_tpl and not self.inimigos):
            self.sala.limpa = True
            if not self.sala.upgrades_ok:
                self.sala.upgrades_ok = True
                tipos = random.sample(POOL_UPGRADES, 2)
                self.sala.pickups.append(Pickup(tipos[0], W / 2 - 95, H / 2))
                self.sala.pickups.append(Pickup(tipos[1], W / 2 + 95, H / 2))
            self.msg('Andar limpo! Pegue suas recompensas e siga em frente.', 200)

        # ---- pickups ----
        for pk in list(self.sala.pickups):
            if math.hypot(pk.x - j.x, pk.y - j.y) < j.raio + 16:
                if pk.aplicar(self):
                    if pk in self.sala.pickups:
                        self.sala.pickups.remove(pk)
                    if pk.kind == 'portal':
                        return

        # ---- partículas e msgs ----
        for pa in self.particulas:
            pa.update()
        self.particulas = [p for p in self.particulas if p.vida > 0]
        if len(self.particulas) > 380:
            self.particulas = self.particulas[-380:]
        for m in self.msgs:
            m['t'] -= 1
        self.msgs = [m for m in self.msgs if m['t'] > 0]

        # ---- vitória / derrota ----
        if self.vitoria_timer > 0:
            self.vitoria_timer -= 1
            if self.vitoria_timer == 0:
                self.estado = 'vitoria'
        if j.coracoes <= 0:
            self.estado = 'gameover'

    def _inimigo_morto(self, ini):
        self.inimigos.remove(ini)
        for _ in range(14):
            self.particulas.append(Particula(ini.x, ini.y, ini.cor))
        if random.random() < 0.30:
            self.sala.pickups.append(Pickup('coracao', ini.x, ini.y))

    def _boss_derrotado(self):
        b = self.boss
        self.boss = None
        self.sala.boss_morto = True
        self.shake = 18
        self.projeteis = [p for p in self.projeteis if p.amigo]  # limpa tiros inimigos
        self.telegrafos.clear()
        for _ in range(60):
            self.particulas.append(Particula(b.x, b.y, b.pcor, vida=random.randint(20, 45)))
        if b.kind == 'diabo':
            self.chave_ceu = True
            self.msg('Você obteve a CHAVE DO CÉU!', 240, grande=True)
            self.sala.pickups.append(Pickup('portal', W / 2, H / 2))
        elif b.kind == 'zeus':
            self.chave_final = True
            self.msg('Você obteve a CHAVE DO SANTUÁRIO!', 240, grande=True)
            self.sala.pickups.append(Pickup('portal', W / 2, H / 2))
        else:
            self.msg('Você derrotou seu reflexo sombrio...', 200, grande=True)
            self.vitoria_timer = 110

    # ============================ DESENHO ============================
    def _texto(self, s, txt, fonte, cx, cy, cor=(255, 255, 255)):
        sombra = fonte.render(txt, True, (10, 10, 16))
        t = fonte.render(txt, True, cor)
        s.blit(sombra, (cx - t.get_width() // 2 + 2, cy + 2))
        s.blit(t, (cx - t.get_width() // 2, cy))

    def _desenhar_fundo(self, s):
        sala = self.sala
        cores = CORES_TEMA[sala.tema]
        s.fill(cores['chao'])
        # textura xadrez leve
        for gx in range(0, W, 64):
            for gy in range(0, H, 64):
                if (gx // 64 + gy // 64) % 2 == 0:
                    pygame.draw.rect(s, cores['det'], (gx, gy, 64, 64))
        # decorações
        for d in sala.deco:
            tipo, x, y = d[0], d[1], d[2]
            if tipo == 'arvore':
                r = d[3]
                pygame.draw.rect(s, (92, 62, 38), (x - 4, y, 8, 16))
                pygame.draw.circle(s, (38, 88, 44), (x, y - 6), r)
                pygame.draw.circle(s, (50, 110, 56), (x - 5, y - 11), r - 5)
            elif tipo == 'flor':
                pygame.draw.circle(s, d[3], (x, y), 4)
                pygame.draw.circle(s, (255, 245, 160), (x, y), 2)
            elif tipo == 'grama':
                pygame.draw.line(s, (46, 96, 50), (x, y), (x - 3, y - 7), 2)
                pygame.draw.line(s, (46, 96, 50), (x, y), (x + 3, y - 7), 2)
            elif tipo == 'lava':
                r = d[3]
                puls = 1 + 0.12 * math.sin(self.frame * 0.06 + x)
                pygame.draw.ellipse(s, (180, 60, 20),
                                    (x - r, y - r * 0.6, r * 2, r * 1.2))
                pygame.draw.ellipse(s, (255, int(120 * puls + 40), 30),
                                    (x - r * 0.6, y - r * 0.35, r * 1.2, r * 0.7))
            elif tipo == 'pedra':
                pygame.draw.circle(s, (70, 50, 46), (x, y), d[3])
                pygame.draw.circle(s, (96, 70, 64), (x - 3, y - 3), d[3] - 4)
            elif tipo == 'osso':
                a = d[3]
                x2 = x + math.cos(a) * 16
                y2 = y + math.sin(a) * 16
                pygame.draw.line(s, (225, 220, 205), (x, y), (x2, y2), 4)
                pygame.draw.circle(s, (225, 220, 205), (int(x), int(y)), 4)
                pygame.draw.circle(s, (225, 220, 205), (int(x2), int(y2)), 4)
            elif tipo == 'nuvem':
                r = d[3]
                pygame.draw.circle(s, (235, 244, 252), (x, y), r)
                pygame.draw.circle(s, (245, 250, 255), (x - r, y + 4), int(r * 0.7))
                pygame.draw.circle(s, (245, 250, 255), (x + r, y + 4), int(r * 0.7))
            elif tipo == 'pilar':
                pygame.draw.rect(s, (172, 192, 222), (x - 10, y - 34, 20, 56))
                pygame.draw.rect(s, (150, 172, 206), (x - 15, y - 40, 30, 8))
                pygame.draw.rect(s, (150, 172, 206), (x - 15, y + 20, 30, 8))
            elif tipo == 'brilho':
                t = (math.sin(self.frame * 0.1 + d[3]) + 1) / 2
                pygame.draw.circle(s, (255, 255, 255), (x, y), 1 + int(t * 2))
            elif tipo == 'runa':
                t = (math.sin(self.frame * 0.05 + d[3]) + 1) / 2
                cor = (int(110 + 90 * t), 50, int(150 + 80 * t))
                pygame.draw.circle(s, cor, (x, y), 11, 2)
                pygame.draw.line(s, cor, (x - 6, y), (x + 6, y), 2)
                pygame.draw.line(s, cor, (x, y - 6), (x, y + 6), 2)
            elif tipo == 'tocha':
                pygame.draw.rect(s, (80, 56, 40), (x - 2, y - 4, 5, 16))
                fl = math.sin(self.frame * 0.25 + d[3]) * 2
                pygame.draw.circle(s, (255, 140, 40), (x, int(y - 9 + fl)), 6)
                pygame.draw.circle(s, (255, 220, 90), (x, int(y - 10 + fl)), 3)

        # paredes (bordas)
        pygame.draw.rect(s, cores['par'], (0, 0, W, 34))
        pygame.draw.rect(s, cores['par'], (0, H - 34, W, 34))
        pygame.draw.rect(s, cores['par'], (0, 0, 34, H))
        pygame.draw.rect(s, cores['par'], (W - 34, 0, 34, H))

    def _desenhar_portas(self, s):
        j = self.jogador
        for porta in self.sala.portas:
            r = porta.rect
            trancada = porta.motivo_tranca(self) is not None
            if porta.lado == 'centro':
                # porta grande do santuário
                pygame.draw.rect(s, (24, 16, 34), r.inflate(18, 14), border_radius=10)
                pygame.draw.rect(s, (52, 36, 76), r, border_radius=8)
                pygame.draw.rect(s, (90, 60, 130), r.inflate(-26, -26), border_radius=8)
                pygame.draw.circle(s, (20, 12, 28), (r.centerx, r.centery + 8), 7)
                if trancada:
                    pygame.draw.line(s, (180, 180, 190), r.topleft, r.bottomright, 5)
                    pygame.draw.line(s, (180, 180, 190), r.topright, r.bottomleft, 5)
                    pygame.draw.circle(s, (255, 210, 80), (r.centerx, r.centery), 11)
                    pygame.draw.rect(s, (255, 210, 80), (r.centerx - 4, r.centery, 8, 13))
                else:
                    puls = (math.sin(self.frame * 0.1) + 1) / 2
                    pygame.draw.rect(s, (150 + int(80 * puls), 80, 220), r.inflate(-26, -26),
                                     3, border_radius=8)
            else:
                cor_porta = (90, 70, 50) if self.sala.tema == 'natureza' else (60, 50, 70)
                pygame.draw.rect(s, cor_porta, r)
                pygame.draw.rect(s, (255, 255, 255), r, 2)
                if trancada:
                    for bx in range(r.left + 14, r.right - 6, 22):
                        pygame.draw.line(s, (200, 200, 210), (bx, r.top + 4),
                                         (bx, r.bottom - 4), 4)
                    pygame.draw.circle(s, (255, 210, 80), r.center, 8)
                else:
                    brilho = (120, 220, 255) if porta.destino.startswith('ceu') else \
                             (255, 140, 60) if porta.destino.startswith('inferno') else (180, 255, 180)
                    puls = 2 + int(2 * (math.sin(self.frame * 0.12) + 1))
                    pygame.draw.rect(s, brilho, r.inflate(puls, puls), 3)
            # rótulo se perto
            if math.hypot(j.x - r.centerx, j.y - r.centery) < 150:
                cy = r.bottom + 6 if r.centery < H // 2 else r.top - 22
                self._texto(s, porta.rotulo, self.f16, r.centerx, cy, (255, 240, 200))

    def _desenhar_hud(self, s):
        j = self.jogador
        # corações
        for i in range(j.max_coracoes):
            x = 30 + i * 26
            y = 26
            cheio = i < j.coracoes
            cor = (235, 70, 90) if cheio else (62, 56, 66)
            pygame.draw.circle(s, cor, (x - 4, y - 2), 6)
            pygame.draw.circle(s, cor, (x + 4, y - 2), 6)
            pygame.draw.polygon(s, cor, [(x - 9, y), (x + 9, y), (x, y + 11)])
        # chaves
        ky = 52
        if self.chave_ceu:
            pygame.draw.circle(s, (255, 215, 80), (32, ky), 6, 3)
            pygame.draw.rect(s, (255, 215, 80), (36, ky - 2, 14, 4))
            s.blit(self.f16.render('Céu', True, (255, 235, 160)), (56, ky - 8))
        if self.chave_final:
            pygame.draw.circle(s, (200, 110, 255), (130, ky), 6, 3)
            pygame.draw.rect(s, (200, 110, 255), (134, ky - 2, 14, 4))
            s.blit(self.f16.render('Santuário', True, (225, 180, 255)), (152, ky - 8))
        # título da sala
        self._texto(s, self.sala.titulo, self.f20, W // 2, 8, (255, 250, 230))
        # barra do boss
        if self.boss:
            bw = 420
            bx = W // 2 - bw // 2
            by = 40
            f = max(0.0, self.boss.hp / self.boss.hpmax)
            pygame.draw.rect(s, (20, 16, 24), (bx - 3, by - 3, bw + 6, 20), border_radius=6)
            pygame.draw.rect(s, (60, 30, 40), (bx, by, bw, 14), border_radius=5)
            pygame.draw.rect(s, (220, 60, 70), (bx, by, int(bw * f), 14), border_radius=5)
            self._texto(s, self.boss.nome, self.f16, W // 2, by + 18, (255, 210, 210))
        # dash cooldown
        if j.dash_cd > 0:
            f = 1 - j.dash_cd / 55
            pygame.draw.rect(s, (40, 40, 56), (30, H - 52, 90, 9), border_radius=4)
            pygame.draw.rect(s, (140, 220, 255), (30, H - 52, int(90 * f), 9), border_radius=4)
        hint = 'WASD mover · Mouse mirar · Clique atirar · ESPAÇO dash · P pausa'
        s.blit(self.f16.render(hint, True, (10, 10, 16)), (32, H - 26))
        s.blit(self.f16.render(hint, True, (235, 235, 245)), (30, H - 28))

    def _desenhar_msgs(self, s):
        y = 86
        for m in self.msgs:
            fonte = self.f28 if m['grande'] else self.f20
            alpha = m['t'] / m['tmax']
            cor = (255, 230, 140) if m['grande'] else (235, 235, 245)
            if alpha < 0.25:
                cor = tuple(int(c * alpha * 4) for c in cor)
            self._texto(s, m['txt'], fonte, W // 2, y, cor)
            y += 34 if m['grande'] else 26

    def draw(self, tela):
        s = self.canvas
        self._desenhar_fundo(s)
        self._desenhar_portas(s)
        for pk in self.sala.pickups:
            pk.desenhar(s, self.f16, self.jogador, self.frame)
        # telégrafos (avisos no chão)
        for tg in self.telegrafos:
            f = 1 - tg['t'] / tg['tmax']
            cor = tg['cor']
            pygame.draw.circle(s, cor, (int(tg['x']), int(tg['y'])), int(tg['r']), 3)
            pygame.draw.circle(s, cor, (int(tg['x']), int(tg['y'])),
                               max(2, int(tg['r'] * f)), 2)
        for ini in self.inimigos:
            ini.desenhar(s)
        if self.boss:
            self.boss.desenhar(s, self.frame)
        for p in self.projeteis:
            p.desenhar(s)
        for pa in self.particulas:
            pa.desenhar(s)
        self.jogador.desenhar(s)
        self._desenhar_hud(s)
        self._desenhar_msgs(s)

        # fade de transição
        if self.fade > 0:
            ov = pygame.Surface((W, H))
            ov.fill((0, 0, 0))
            ov.set_alpha(int(255 * self.fade / 25))
            s.blit(ov, (0, 0))

        # overlays de estado
        if self.estado == 'pausa':
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 10, 150))
            s.blit(ov, (0, 0))
            self._texto(s, 'PAUSADO', self.f44, W // 2, H // 2 - 40)
            self._texto(s, 'P para continuar', self.f20, W // 2, H // 2 + 14)
        elif self.estado == 'gameover':
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((20, 0, 0, 175))
            s.blit(ov, (0, 0))
            self._texto(s, 'VOCÊ MORREU', self.f44, W // 2, H // 2 - 60, (255, 90, 90))
            self._texto(s, 'O mundo permanece dividido entre o Inferno e o Céu...',
                        self.f20, W // 2, H // 2)
            self._texto(s, 'Pressione R para tentar de novo', self.f20, W // 2, H // 2 + 36,
                        (255, 230, 150))
        elif self.estado == 'vitoria':
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((10, 8, 30, 185))
            s.blit(ov, (0, 0))
            self._texto(s, 'VITÓRIA!', self.f44, W // 2, H // 2 - 90, (255, 225, 120))
            self._texto(s, 'Você derrotou o Diabo, Zeus e o seu próprio reflexo sombrio.',
                        self.f20, W // 2, H // 2 - 28)
            tempo = self.frame // FPS
            self._texto(s, f'Tempo: {tempo // 60:02d}:{tempo % 60:02d}   ·   Upgrades: {self.upgrades_pegos}',
                        self.f20, W // 2, H // 2 + 8, (200, 220, 255))
            self._texto(s, 'Pressione R para jogar de novo', self.f20, W // 2, H // 2 + 52,
                        (255, 230, 150))

        # shake
        ox = oy = 0
        if self.shake > 0:
            ox = random.randint(-self.shake, self.shake) // 2
            oy = random.randint(-self.shake, self.shake) // 2
        tela.fill((0, 0, 0))
        tela.blit(s, (ox, oy))


# ============================================================ MAIN
def main():
    pygame.init()
    tela = pygame.display.set_mode((W, H))
    pygame.display.set_caption('Mago: Entre o Inferno e o Céu')
    clock = pygame.time.Clock()
    game = Game()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.evento(e)
        if game.reiniciar:
            game = Game()
        game.update()
        game.draw(tela)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == '__main__':
    main()