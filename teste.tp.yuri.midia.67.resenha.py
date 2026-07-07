import pygame
from sys import exit
import math
import os
import random
from collections import deque
from settings import *

pygame.init()

screen = pygame.display.set_mode((LARGURA, ALTURA))
pygame.display.set_caption('Jogo Bicalho')
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


TILE_SIZE = 16
TILE = TILE_SIZE * TILE_SCALE

TELEPORTE_ID = 99
TELEPORTE_MAPA1_POS = None
TELEPORTE_MAPA1_CANTO = "superior-esquerdo"
MAPA2_COLUNAS, MAPA2_LINHAS = 30, 20
MAPA2_PISO = 18

WALKABLE = {18, 27, 69, 70, 71, TELEPORTE_ID}

def carregar_tileset(nome, tile_px=TILE_SIZE):
    for base in (BASE_DIR, os.path.dirname(BASE_DIR)):
        caminho = os.path.join(base, nome)
        if os.path.exists(caminho):
            img = pygame.image.load(caminho).convert_alpha()
            return img, img.get_width() // tile_px, tile_px
    raise FileNotFoundError(nome)

TS_MAPA1 = carregar_tileset("tileset.png")
TS_GRASS = carregar_tileset("TX Tileset Grass.png", 32)
TS_WALL  = carregar_tileset("TX Tileset Wall.png", 32)
TS_PLANT = carregar_tileset("TX Plant.png", 32)

tileset_img, TILESET_COLUNAS, _ = TS_MAPA1


def carregar_csv(caminho):
    mapa = []
    arquivo = open(caminho)
    for linha in arquivo:
        linha = linha.strip().rstrip(",")
        if linha != "":
            numeros = []
            for pedaco in linha.split(","):
                numeros.append(int(pedaco))
            mapa.append(numeros)
    arquivo.close()
    return mapa


def pegar_tile(tile_id, tileset=None, colunas=None, tile_px=TILE_SIZE):
    if tileset is None:
        tileset, colunas, tile_px = tileset_img, TILESET_COLUNAS, TILE_SIZE
    indice = tile_id - 1
    coluna = indice % colunas
    linha  = indice // colunas
    area = pygame.Rect(coluna * tile_px, linha * tile_px, tile_px, tile_px)
    tile = tileset.subsurface(area)
    return pygame.transform.scale(tile, (TILE, TILE))


def achar_tile(mapa, tile_id):
    for y, linha in enumerate(mapa):
        for x, t in enumerate(linha):
            if t == tile_id:
                return (x, y)
    return None


def celulas_alcancaveis(mapa, col, row):
    rows = len(mapa)
    if not (0 <= row < rows and 0 <= col < len(mapa[row]) and mapa[row][col] in WALKABLE):
        return set()
    visto = {(col, row)}
    fila = deque([(col, row)])
    while fila:
        cx, cy = fila.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if (0 <= ny < rows and 0 <= nx < len(mapa[ny])
                    and (nx, ny) not in visto and mapa[ny][nx] in WALKABLE):
                visto.add((nx, ny))
                fila.append((nx, ny))
    return visto


def posicao_portal_canto(mapa, spawn_col, spawn_row, canto):
    rows = len(mapa)
    cols = max(len(l) for l in mapa)
    cantos = {
        "superior-esquerdo": (0, 0),
        "superior-direito":  (cols - 1, 0),
        "inferior-esquerdo": (0, rows - 1),
        "inferior-direito":  (cols - 1, rows - 1),
    }
    alvo = cantos.get(canto, (0, 0))
    reg = celulas_alcancaveis(mapa, spawn_col, spawn_row)
    reg.discard((spawn_col, spawn_row))
    if not reg:
        return None
    return min(reg, key=lambda c: abs(c[0] - alvo[0]) + abs(c[1] - alvo[1]))


def surface_teleporte():
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    centro = (TILE // 2, TILE // 2)
    pygame.draw.circle(surf, (60, 20, 90),    centro, TILE // 2)
    pygame.draw.circle(surf, (150, 70, 230),  centro, TILE // 2 - 3)
    pygame.draw.circle(surf, (225, 190, 255), centro, TILE // 4)
    return surf


mapa_csv = carregar_csv(os.path.join(BASE_DIR, "mapa 1.csv"))

start_col = int(PLAYER_START_X // TILE)
start_row = int(PLAYER_START_Y // TILE)
if achar_tile(mapa_csv, TELEPORTE_ID) is None:
    if TELEPORTE_MAPA1_POS:
        pos = TELEPORTE_MAPA1_POS
    else:
        pos = posicao_portal_canto(mapa_csv, start_col, start_row, TELEPORTE_MAPA1_CANTO)
    if pos:
        mapa_csv[pos[1]][pos[0]] = TELEPORTE_ID

chao2 = carregar_csv(os.path.join(BASE_DIR, "mapa 3_chao.csv"))
mapa2 = carregar_csv(os.path.join(BASE_DIR, "mapa 3_parede.csv"))
obj_path = os.path.join(BASE_DIR, "mapa 3_obj.csv")
obj2 = carregar_csv(obj_path) if os.path.exists(obj_path) else None
mapa2[len(mapa2) // 2][len(mapa2[0]) // 2] = TELEPORTE_ID
WALKABLE2 = {-1, TELEPORTE_ID}

PORTAL_SURF = surface_teleporte()

mapas            = [mapa_csv, mapa2]
chaos            = [None, chao2]
objs             = [None, obj2]
walkables_mapas  = [WALKABLE, WALKABLE2]
ts_principal_mapas = [TS_MAPA1, TS_WALL]
ts_chao_mapas      = [None,     TS_GRASS]
ts_obj_mapas       = [None,     TS_PLANT]
mapw_mapas       = [len(mapa_csv[0]) * TILE, len(mapa2[0]) * TILE]
maph_mapas       = [len(mapa_csv) * TILE,    len(mapa2) * TILE]
teleportes_mapas = [achar_tile(mapa_csv, TELEPORTE_ID), achar_tile(mapa2, TELEPORTE_ID)]


def gerar_hitboxes(mapa, walkable):
    hitboxes = []
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            tile_id = mapa[y][x]
            if tile_id not in walkable:
                parede = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                hitboxes.append(parede)
    return hitboxes


hitboxes_mapas = [gerar_hitboxes(m, w) for m, w in zip(mapas, walkables_mapas)]


class Mundo:
    def __init__(self, indice=0):
        self.ir_para(indice)

    def ir_para(self, indice):
        self.indice  = indice
        self.mapa = mapas[indice]
        self.chao = chaos[indice]
        self.obj = objs[indice]
        self.hitboxes = hitboxes_mapas[indice]
        self.ts_principal = ts_principal_mapas[indice]
        self.ts_chao = ts_chao_mapas[indice]
        self.ts_obj = ts_obj_mapas[indice]
        self.largura = mapw_mapas[indice]
        self.altura = maph_mapas[indice]
        self.teleporte = teleportes_mapas[indice]

mundo = Mundo(0)


def trocar_mapa():
    mundo.ir_para(1 - mundo.indice)
    col, row = mundo.teleporte
    player.pos.x = col * TILE + TILE // 2
    player.pos.y = row * TILE + TILE // 2
    player.hitbox_rect.center = (int(player.pos.x), int(player.pos.y))
    player.rect.center = player.hitbox_rect.center
    player.desencostar_paredes()
    spawner.iniciar(mundo.indice)


def desenhar_camada(surface, mapa, offset, ts):
    tileset, colunas, tile_px = ts
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            tile_id = mapa[y][x]
            if tile_id <= 0:
                continue
            if tile_id == TELEPORTE_ID:
                tile = PORTAL_SURF
            else:
                tile = pegar_tile(tile_id, tileset, colunas, tile_px)
            surface.blit(tile, (x * TILE - offset.x, y * TILE - offset.y))


def desenhar_mapa(surface, chao, mapa, offset, ts_chao, ts_principal):
    if chao is not None:
        desenhar_camada(surface, chao, offset, ts_chao)
    desenhar_camada(surface, mapa, offset, ts_principal)


IDLE_FRAMES = 15
WALK_FRAMES = 15
ATTACK_FRAMES = 15
ANIM_SPEED = 0.15

LINHA_POR_SETOR = [0, 1, 2, 3, 4, 5, 6, 7]

def carregar_animacao(nome_arquivo, num_frames, escala, colunas=15, linhas=8, fallback="hero.png"):
    caminho = os.path.join(BASE_DIR, nome_arquivo)

    if os.path.exists(caminho):
        sheet = pygame.image.load(caminho).convert_alpha()
        fw = sheet.get_width() // colunas
        fh = sheet.get_height() // linhas
        direcoes = []
        for linha in range(linhas):
            frames = []
            for coluna in range(num_frames):
                frame = pygame.Surface((fw, fh), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), pygame.Rect(coluna * fw, linha * fh, fw, fh))
                frames.append(pygame.transform.rotozoom(frame, 0, escala))
            direcoes.append(frames)
        return direcoes

    img = pygame.image.load(os.path.join(BASE_DIR, fallback)).convert_alpha()
    frame = pygame.transform.rotozoom(img, 0, escala)
    return [[frame] for _ in range(8)]

def normalizar_frames(animations):
    todos = [f for direcoes in animations.values() for frames in direcoes for f in frames]
    maxw = max(f.get_width()  for f in todos)
    maxh = max(f.get_height() for f in todos)
    for estado, direcoes in animations.items():
        novas_direcoes = []
        for frames in direcoes:
            novos = []
            for f in frames:
                canvas = pygame.Surface((maxw, maxh), pygame.SRCALPHA)
                canvas.blit(f, ((maxw - f.get_width())  // 2,
                                (maxh - f.get_height()) // 2))
                novos.append(canvas)
            novas_direcoes.append(novos)
        animations[estado] = novas_direcoes
    return animations


all_sprites_group  = pygame.sprite.Group()
bullet_group       = pygame.sprite.Group()
enemy_group        = pygame.sprite.Group()
enemy_bullet_group = pygame.sprite.Group()
item_group         = pygame.sprite.Group()

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()

        self.animations = {
            'idle':   carregar_animacao('Idle_Shadowless.png',      IDLE_FRAMES,   PLAYER_SIZE),
            'walk':   carregar_animacao('Walk_Shadowless.png',      WALK_FRAMES,   PLAYER_SIZE),
            'attack': carregar_animacao('CastSpell_Shadowless.png', ATTACK_FRAMES, PLAYER_SIZE),
        }
        self.animations = normalizar_frames(self.animations)

        self.state        = 'idle'
        self.frame_index  = 0.0
        self.attacking    = False
        self.angle        = 0
        self.direcao      = 2

        self.base_player_image = self.animations['idle'][self.direcao][0]
        self.image = self.base_player_image

        self.pos = pygame.math.Vector2(PLAYER_START_X, PLAYER_START_Y)
        self.hitbox_rect = pygame.Rect(0, 0, 40, 52)
        self.hitbox_rect.center = self.pos
        self.rect = self.hitbox_rect.copy()

        self.shoot = False
        self.speed = PLAYER_SPEED
        self.shot_cooldown = 0
        self.gun_barrel_offset = pygame.math.Vector2(GUN_OFFSET_X, GUNOFFSET_Y)

        self.acabou_de_teleportar = False

        self.max_health = 10
        self.health = self.max_health
        self.dano_cooldown = 0

        self.moedas = 0
        self.tem_chave = False
        self.no_portal = False

    def player_aim(self):
        self.mouse_coords = pygame.mouse.get_pos()
        self.x_change_mouse_player = self.mouse_coords[0] - LARGURA // 2
        self.y_change_mouse_player = self.mouse_coords[1] - ALTURA  // 2
        self.angle = math.degrees(
            math.atan2(self.y_change_mouse_player, self.x_change_mouse_player))

        setor = round(self.angle / 45) % 8
        self.direcao = LINHA_POR_SETOR[setor]

        self.image = self.base_player_image
        self.rect = self.image.get_rect(center=self.hitbox_rect.center)

    def user_input(self):
        self.velocity_x = 0
        self.velocity_y = 0

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: self.velocity_y = -self.speed
        if keys[pygame.K_s]: self.velocity_y =  self.speed
        if keys[pygame.K_a]: self.velocity_x = -self.speed
        if keys[pygame.K_d]: self.velocity_x =  self.speed

        if self.velocity_x != 0 and self.velocity_y != 0:
            self.velocity_x /= math.sqrt(2)
            self.velocity_y /= math.sqrt(2)

        if pygame.mouse.get_pressed()[0] or keys[pygame.K_SPACE]:
            self.shoot = True
            self.is_shooting()
        else:
            self.shoot = False

    def is_shooting(self):
        if self.shot_cooldown == 0:
            self.shot_cooldown = SHOOT_COOLDOWN
            spawn_pos = self.pos + self.gun_barrel_offset.rotate(self.angle)
            bullet = Bullet(spawn_pos.x, spawn_pos.y, self.angle)
            bullet_group.add(bullet)
            all_sprites_group.add(bullet)
            self.attacking   = True
            self.frame_index = 0.0

    def set_state(self):
        if self.attacking:
            novo = 'attack'
        elif self.velocity_x != 0 or self.velocity_y != 0:
            novo = 'walk'
        else:
            novo = 'idle'

        if novo != self.state:
            self.state = novo
            self.frame_index = 0.0

    def animate(self):
        animation = self.animations[self.state][self.direcao]

        if self.state == 'attack':
            velocidade = len(animation) / max(SHOOT_COOLDOWN, 1)
        else:
            velocidade = ANIM_SPEED
        self.frame_index += velocidade
        if self.frame_index >= len(animation):
            self.frame_index = 0.0
            if self.state == 'attack':
                self.attacking = False

        self.base_player_image = animation[int(self.frame_index)]

    def move(self):
        self.pos.x += self.velocity_x
        self.hitbox_rect.centerx = int(self.pos.x)
        for box in mundo.hitboxes:
            if self.hitbox_rect.colliderect(box):
                if self.velocity_x > 0:
                    self.hitbox_rect.right = box.left
                else:
                    self.hitbox_rect.left  = box.right
                self.pos.x = self.hitbox_rect.centerx

        self.pos.y += self.velocity_y
        self.hitbox_rect.centery = int(self.pos.y)
        for box in mundo.hitboxes:
            if self.hitbox_rect.colliderect(box):
                if self.velocity_y > 0:
                    self.hitbox_rect.bottom = box.top
                else:
                    self.hitbox_rect.top    = box.bottom
                self.pos.y = self.hitbox_rect.centery

        self.rect.center = self.hitbox_rect.center

    def desencostar_paredes(self):
        for box in mundo.hitboxes:
            if self.hitbox_rect.colliderect(box):
                dx_esq   = box.right - self.hitbox_rect.left
                dx_dir   = self.hitbox_rect.right - box.left
                dy_cima  = box.bottom - self.hitbox_rect.top
                dy_baixo = self.hitbox_rect.bottom - box.top
                menor = min(dx_esq, dx_dir, dy_cima, dy_baixo)
                if   menor == dy_cima:  self.hitbox_rect.top    = box.bottom
                elif menor == dy_baixo: self.hitbox_rect.bottom = box.top
                elif menor == dx_esq:   self.hitbox_rect.left   = box.right
                else:                   self.hitbox_rect.right  = box.left
        self.pos.x = self.hitbox_rect.centerx
        self.pos.y = self.hitbox_rect.centery
        self.rect.center = self.hitbox_rect.center

    def checar_teleporte(self):
        col = self.hitbox_rect.centerx // TILE
        row = self.hitbox_rect.centery // TILE
        em_cima = (0 <= row < len(mundo.mapa) and 0 <= col < len(mundo.mapa[row])
                   and mundo.mapa[row][col] == TELEPORTE_ID)
        self.no_portal = em_cima

        if em_cima:
            if self.tem_chave and not self.acabou_de_teleportar:
                trocar_mapa()
                self.acabou_de_teleportar = True
        else:
            self.acabou_de_teleportar = False

    def update(self):
        self.user_input()
        self.move()
        self.checar_teleporte()
        self.set_state()
        self.animate()
        self.player_aim()
        if self.shot_cooldown > 0:
            self.shot_cooldown -= 1
        if self.dano_cooldown > 0:
            self.dano_cooldown -= 1


class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, angle):
        super().__init__()
        self.image = pygame.transform.rotozoom(
            pygame.image.load("1.png").convert_alpha(), 0, BULLET_SCALE)
        self.rect  = self.image.get_rect(center=(x, y))
        self.x, self.y = float(x), float(y)
        self.angle = angle
        self.x_vel = math.cos(math.radians(angle)) * BULLET_SPEED
        self.y_vel = math.sin(math.radians(angle)) * BULLET_SPEED
        self.spawn_time = pygame.time.get_ticks()
        self.damage = 1

    def update(self):
        self.x += self.x_vel
        self.y += self.y_vel
        self.rect.center = (int(self.x), int(self.y))
        if pygame.time.get_ticks() - self.spawn_time > BULLET_LIFETIME:
            self.kill()


NECRO_POS = (400, 400)
NEC_VIDA,   NEC_DANO,   NEC_ATAQUE   = 5,  1, 45
FRACO_VIDA, FRACO_DANO, FRACO_ATAQUE = 2,  1, 90
MIN_VIDA,   MIN_DANO,   MIN_ATAQUE   = 4,  1, 55
BOSS_VIDA,  BOSS_DANO,  BOSS_ATAQUE  = 40, 1, 40

FRACO_SPEED = 3
BOSS_SPEED  = 2

FRACO_MOEDAS, MIN_MOEDAS, BOSS_MOEDAS = 1, 2, 10

KILLS_PARA_CHAVE  = 5
COOLDOWN_POS_META = 6000
MAX_VIVOS         = 4

SPAWN_FRACO_INTERVALO  = 4000
SPAWN_MINION_INTERVALO = 2500
BOSS_DELAY             = 12000
AVISO_DURACAO          = 800
SPAWN_GRACA            = 4000


BOSS_ESCALA     = 2.5
MINION_ESCALA   = 1.1
BOSS_ANIM_SPEED = 0.2
BOSS_WINDUP     = 500


def carregar_sheet(nome, colunas, linhas, num_frames, escala):
    caminho = os.path.join(BASE_DIR, nome)
    sheet = pygame.image.load(caminho).convert_alpha()
    fw = sheet.get_width() // colunas
    fh = sheet.get_height() // linhas
    frames = []
    for i in range(num_frames):
        c, r = i % colunas, i // colunas
        f = pygame.Surface((fw, fh), pygame.SRCALPHA)
        f.blit(sheet, (0, 0), pygame.Rect(c * fw, r * fh, fw, fh))
        frames.append(pygame.transform.rotozoom(f, 0, escala))
    return frames


BOSS_FRAMES   = carregar_sheet('AngelsSpriteSheetNew.png', 8, 1, 8, BOSS_ESCALA)
MINION_FRAMES = carregar_sheet('boss_idle.png', 5, 1, 4, MINION_ESCALA)

BAT_ESCALA       = 1.2
BAT_OLHA_DIREITA = True
FRACO_FRAMES = carregar_sheet('Bat_Fly.png', 4, 1, 4, BAT_ESCALA)
if not BAT_OLHA_DIREITA:
    FRACO_FRAMES = [pygame.transform.flip(f, True, False) for f in FRACO_FRAMES]

MINION_ATTACK_FRAMES = carregar_sheet('boss_attack.png', 6, 3, 13, MINION_ESCALA)
BAT_ATTACK_FRAMES = carregar_sheet('Bat_Attack.png', 4, 2, 7, BAT_ESCALA)
if not BAT_OLHA_DIREITA:
    BAT_ATTACK_FRAMES = [pygame.transform.flip(f, True, False) for f in BAT_ATTACK_FRAMES]

FRACO_ALCANCE = 46
MIN_ALCANCE   = 58
BOSS_ALCANCE  = 70
ATAQUE_MARGEM = 8

BOSS_TIRO_INTERVALO  = 2000
BOSS_TIRO_DANO       = 3
BOSS_BULLET_SPEED    = 7
BOSS_BULLET_LIFETIME = 4000


def surface_boss_bullet():
    r = 14
    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 120, 40),  (r, r), r)
    pygame.draw.circle(surf, (255, 225, 130), (r, r), r // 2)
    return surf


BOSS_BULLET_SURF = surface_boss_bullet()


def posicao_spawn(mapa_indice, dist_min_tiles=6):
    mapa = mapas[mapa_indice]
    walk = walkables_mapas[mapa_indice]
    pcol = player.hitbox_rect.centerx // TILE
    prow = player.hitbox_rect.centery // TILE

    longe, qualquer = [], []
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            if mapa[y][x] in walk and mapa[y][x] != TELEPORTE_ID:
                qualquer.append((x, y))
                if abs(x - pcol) + abs(y - prow) >= dist_min_tiles:
                    longe.append((x, y))
    candidatos = longe or qualquer
    col, row = random.choice(candidatos)
    return (col * TILE + TILE // 2, row * TILE + TILE // 2)


class Enemy(pygame.sprite.Sprite):
    def __init__(self, position, mapa=0, vida=5, dano=1, velocidade=ENEMY_SPEED,
                 escala=2, imagem='0.png', ataque_delay=45, moedas=1,
                 frames=None, anim_speed=0.15, virar=True,
                 frames_attack=None, attack_speed=0.35, alcance=44):
        super().__init__(enemy_group, all_sprites_group)
        self.mapa = mapa
        self.frames = frames
        self.frame_index = 0.0
        self.anim_speed = anim_speed
        self.virar = virar
        self.frames_attack = frames_attack
        self.attack_speed = attack_speed
        self.attack_index = 0.0
        self.atacando = False
        self.alcance = alcance
        if frames:
            self.image = frames[0]
        else:
            self.image = pygame.transform.rotozoom(
                pygame.image.load(imagem).convert_alpha(), 0, escala)
        self.rect  = self.image.get_rect(center=position)
        self.position  = pygame.math.Vector2(position)
        self.direction = pygame.math.Vector2()
        self.speed = velocidade
        self.max_health = vida
        self.health = vida
        self.dano = dano
        self.moedas = moedas
        self.ataque_delay = ataque_delay
        self.ataque_cooldown = 0

    def hunt_player(self):
        pv = pygame.math.Vector2(player.hitbox_rect.center)
        ev = pygame.math.Vector2(self.rect.center)
        delta = pv - ev
        dist = delta.magnitude()
        if dist > self.alcance:
            passo = min(self.speed, dist - self.alcance)
            self.direction = delta.normalize()
            self.position += self.direction * passo
            self.rect.center = (int(self.position.x), int(self.position.y))

    def atacar(self):
        if self.frames_attack:
            self.atacando = True
            self.attack_index = 0.0

    def animar(self):
        if self.atacando and self.frames_attack:
            self.attack_index += self.attack_speed
            if self.attack_index >= len(self.frames_attack):
                self.atacando = False
                self.frame_index = 0.0
                base = self.frames[0] if self.frames else self.image
            else:
                base = self.frames_attack[int(self.attack_index)]
        elif self.frames:
            self.frame_index += self.anim_speed
            if self.frame_index >= len(self.frames):
                self.frame_index = 0.0
            base = self.frames[int(self.frame_index)]
        else:
            return
        if self.virar and player.hitbox_rect.centerx < self.position.x:
            base = pygame.transform.flip(base, True, False)
        self.image = base
        self.rect = self.image.get_rect(center=(int(self.position.x), int(self.position.y)))

    def levar_dano(self, dano):
        self.health -= dano
        if self.health <= 0:
            self.kill()
            return True
        return False

    def update(self):
        if not self.atacando:
            self.hunt_player()
        self.animar()
        if self.ataque_cooldown > 0:
            self.ataque_cooldown -= 1


class Boss(Enemy):
    def __init__(self, position, mapa):
        super().__init__(position, mapa=mapa, vida=BOSS_VIDA, dano=BOSS_DANO,
                         velocidade=BOSS_SPEED, ataque_delay=BOSS_ATAQUE,
                         moedas=BOSS_MOEDAS, frames=BOSS_FRAMES,
                         anim_speed=BOSS_ANIM_SPEED, virar=False,
                         alcance=BOSS_ALCANCE)
        self.ultimo_tiro = pygame.time.get_ticks()
        self.carregando = False
        self.inicio_carga = 0

    def update(self):
        agora = pygame.time.get_ticks()

        if self.carregando:
            self.animar()
            if self.ataque_cooldown > 0:
                self.ataque_cooldown -= 1
            if agora - self.inicio_carga >= BOSS_WINDUP:
                EnemyBullet(self.rect.centerx, self.rect.centery,
                            player.hitbox_rect.center, BOSS_TIRO_DANO)
                self.carregando = False
                self.ultimo_tiro = agora
        else:
            super().update()
            if agora - self.ultimo_tiro >= BOSS_TIRO_INTERVALO:
                self.carregando = True
                self.inicio_carga = agora


class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, alvo, dano):
        super().__init__(enemy_bullet_group, all_sprites_group)
        self.image = BOSS_BULLET_SURF
        self.rect  = self.image.get_rect(center=(x, y))
        self.x, self.y = float(x), float(y)
        direcao = pygame.math.Vector2(alvo) - pygame.math.Vector2(x, y)
        if direcao.length() > 0:
            direcao = direcao.normalize()
        self.vel = direcao * BOSS_BULLET_SPEED
        self.dano = dano
        self.spawn_time = pygame.time.get_ticks()

    def update(self):
        self.x += self.vel.x
        self.y += self.vel.y
        self.rect.center = (int(self.x), int(self.y))
        if pygame.time.get_ticks() - self.spawn_time > BOSS_BULLET_LIFETIME:
            self.kill()


CHAVE_ESCALA = 2.5
CHAVE_ANIM_SPEED = 0.2
CHAVE_FRAMES = carregar_sheet('KeyString.png', 1, 11, 11, CHAVE_ESCALA)


class Chave(pygame.sprite.Sprite):
    def __init__(self, position):
        super().__init__(item_group, all_sprites_group)
        self.frame_index = 0.0
        self.image = CHAVE_FRAMES[0]
        self.rect  = self.image.get_rect(center=position)

    def update(self):
        self.frame_index += CHAVE_ANIM_SPEED
        if self.frame_index >= len(CHAVE_FRAMES):
            self.frame_index = 0.0
        centro = self.rect.center
        self.image = CHAVE_FRAMES[int(self.frame_index)]
        self.rect = self.image.get_rect(center=centro)


class Camera(pygame.sprite.Group):
    def __init__(self):
        super().__init__()
        self.offset = pygame.math.Vector2()

    def custom_draw(self):
        self.offset.x = player.rect.centerx - LARGURA // 2
        self.offset.y = player.rect.centery  - ALTURA  // 2

        self.offset.x = max(0, min(self.offset.x, mundo.largura - LARGURA))
        self.offset.y = max(0, min(self.offset.y, mundo.altura  - ALTURA))

        desenhar_mapa(screen, mundo.chao, mundo.mapa, self.offset,
                      mundo.ts_chao, mundo.ts_principal)

        spawner.desenhar_avisos(screen, self.offset)

        for sprite in all_sprites_group:
            screen.blit(sprite.image, sprite.rect.topleft - self.offset)

        if mundo.obj is not None:
            desenhar_camada(screen, mundo.obj, self.offset, mundo.ts_obj)


class GerenciadorSpawn:
    def __init__(self):
        self.iniciar(mundo.indice)

    def iniciar(self, mapa_indice):
        for inimigo in list(enemy_group):
            inimigo.kill()
        for tiro in list(enemy_bullet_group):
            tiro.kill()
        for item in list(item_group):
            item.kill()
        self.mapa        = mapa_indice
        self.inicio      = pygame.time.get_ticks()
        self.ultimo      = self.inicio
        self.boss_criado = False
        self.avisos      = []
        self.kills       = 0
        self.chave_dropada = False
        self.pausa_ate   = 0
        player.tem_chave = False

    def agendar(self, pos, criar, raio):
        self.avisos.append({
            'pos':    pos,
            'raio':   raio,
            'quando': pygame.time.get_ticks() + AVISO_DURACAO,
            'criar':  criar,
        })

    def registrar_kill(self, inimigo):
        self.kills += 1
        if not self.chave_dropada and self.kills >= KILLS_PARA_CHAVE:
            Chave(inimigo.rect.center)
            self.chave_dropada = True
            self.pausa_ate = pygame.time.get_ticks() + COOLDOWN_POS_META

    def update(self):
        agora = pygame.time.get_ticks()

        for aviso in list(self.avisos):
            if agora >= aviso['quando']:
                aviso['criar'](aviso['pos'])
                self.avisos.remove(aviso)

        if agora - self.inicio < SPAWN_GRACA:
            return
        if agora < self.pausa_ate:
            return
        if len(enemy_group) + len(self.avisos) >= MAX_VIVOS:
            return

        if self.mapa == 0:
            if agora - self.ultimo >= SPAWN_FRACO_INTERVALO:
                self.agendar(
                    posicao_spawn(0),
                    lambda p: Enemy(p, mapa=0, vida=FRACO_VIDA, dano=FRACO_DANO,
                                    velocidade=FRACO_SPEED, ataque_delay=FRACO_ATAQUE,
                                    moedas=FRACO_MOEDAS, frames=FRACO_FRAMES,
                                    frames_attack=BAT_ATTACK_FRAMES, alcance=FRACO_ALCANCE),
                    TILE // 2)
                self.ultimo = agora
        elif self.mapa == 1:
            if not self.boss_criado and agora - self.ultimo >= SPAWN_MINION_INTERVALO:
                self.agendar(
                    posicao_spawn(1),
                    lambda p: Enemy(p, mapa=1, vida=MIN_VIDA, dano=MIN_DANO,
                                    velocidade=ENEMY_SPEED, ataque_delay=MIN_ATAQUE,
                                    moedas=MIN_MOEDAS, frames=MINION_FRAMES,
                                    frames_attack=MINION_ATTACK_FRAMES, alcance=MIN_ALCANCE),
                    TILE // 2)
                self.ultimo = agora
            if not self.boss_criado and agora - self.inicio >= BOSS_DELAY:
                self.agendar(
                    posicao_spawn(1, dist_min_tiles=8),
                    lambda p: Boss(p, mapa=1),
                    70)
                self.boss_criado = True

    def desenhar_avisos(self, surface, offset):
        agora = pygame.time.get_ticks()
        for aviso in self.avisos:
            raio = aviso['raio']
            falta = max(0, aviso['quando'] - agora)
            progresso = 1 - falta / AVISO_DURACAO
            cx = int(aviso['pos'][0] - offset.x)
            cy = int(aviso['pos'][1] - offset.y)
            circ = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
            pygame.draw.circle(circ, (255, 40, 40, 110), (raio, raio), int(raio * progresso))
            pygame.draw.circle(circ, (255, 40, 40, 200), (raio, raio), raio, 3)
            surface.blit(circ, (cx - raio, cy - raio))


def desenhar_barra_vida(surface, x, y, largura, altura, vida, vida_max):
    if vida < 0:
        vida = 0
    fracao = vida / vida_max
    pygame.draw.rect(surface, (90, 20, 20), (x, y, largura, altura))
    pygame.draw.rect(surface, (40, 200, 60), (x, y, int(largura * fracao), altura))
    pygame.draw.rect(surface, (15, 15, 15), (x, y, largura, altura), 2)


player      = Player()
camera      = Camera()
all_sprites_group.add(player)

spawner = GerenciadorSpawn()

ENEMY_DANO_COOLDOWN = 45

fonte_hud = pygame.font.SysFont("arial", 24, bold=True)
fonte_pequena = pygame.font.SysFont("arial", 18)


def tela_inicio():
    fonte_titulo = pygame.font.SysFont("arialblack", 96)
    fonte_botao  = pygame.font.SysFont("arial", 40, bold=True)

    titulo = fonte_titulo.render("THE ADVENTURER", True, (240, 230, 200))
    titulo_rect = titulo.get_rect(center=(LARGURA // 2, ALTURA // 2 - 90))

    texto_botao = fonte_botao.render("Comecar Jogo Novo", True, (255, 255, 255))
    botao_rect = texto_botao.get_rect(center=(LARGURA // 2, ALTURA // 2 + 80))
    fundo_botao = botao_rect.inflate(60, 30)   

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if fundo_botao.collidepoint(event.pos):
                    return
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return

        mouse = pygame.mouse.get_pos()
        hover = fundo_botao.collidepoint(mouse)

        screen.fill((20, 18, 30))
        screen.blit(titulo, titulo_rect)
        pygame.draw.rect(screen, (90, 60, 140) if hover else (55, 40, 90), fundo_botao, border_radius=10)
        pygame.draw.rect(screen, (200, 180, 240), fundo_botao, 3, border_radius=10)
        screen.blit(texto_botao, botao_rect)

        pygame.display.update()
        clock.tick(FPS)


tela_inicio()


def reiniciar_jogo():
    for b in bullet_group:
        b.kill()
    mundo.ir_para(0)

    player.health = player.max_health
    player.dano_cooldown = 0
    player.shot_cooldown = 0
    player.acabou_de_teleportar = False
    player.moedas = 0
    player.pos = pygame.math.Vector2(PLAYER_START_X, PLAYER_START_Y)
    player.hitbox_rect.center = (int(player.pos.x), int(player.pos.y))
    player.rect.center = player.hitbox_rect.center

    spawner.iniciar(0)


def tela_game_over():

    fonte_titulo = pygame.font.SysFont("arialblack", 96)
    fonte_botao  = pygame.font.SysFont("arial", 40, bold=False)

    titulo = fonte_titulo.render("GAME OVER", True, (230, 60, 60))
    titulo_rect = titulo.get_rect(center=(LARGURA // 2, ALTURA // 2 - 90))

    texto_jogar = fonte_botao.render("Jogar de Novo", True, (255, 255, 255))
    jogar_rect = texto_jogar.get_rect(center=(LARGURA // 2, ALTURA // 2 + 55))
    fundo_jogar = jogar_rect.inflate(60, 30)

    texto_sair = fonte_botao.render("Sair", True, (255, 255, 255))
    sair_rect = texto_sair.get_rect(center=(LARGURA // 2, ALTURA // 2 + 175))
    fundo_sair = sair_rect.inflate(60, 30)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if fundo_jogar.collidepoint(event.pos):
                    return
                if fundo_sair.collidepoint(event.pos):
                    pygame.quit()
                    exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    return
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    exit()

        mouse = pygame.mouse.get_pos()
        hover_jogar = fundo_jogar.collidepoint(mouse)
        hover_sair  = fundo_sair.collidepoint(mouse)

        screen.fill((20, 10, 10))
        screen.blit(titulo, titulo_rect)
        pygame.draw.rect(screen, (120, 60, 60) if hover_jogar else (80, 40, 40), fundo_jogar, border_radius=10)
        pygame.draw.rect(screen, (240, 180, 180), fundo_jogar, 3, border_radius=10)
        screen.blit(texto_jogar, jogar_rect)
        pygame.draw.rect(screen, (120, 60, 60) if hover_sair else (80, 40, 40), fundo_sair, border_radius=10)
        pygame.draw.rect(screen, (240, 180, 180), fundo_sair, 3, border_radius=10)
        screen.blit(texto_sair, sair_rect)

        pygame.display.update()
        clock.tick(FPS)


def tela_vitoria():
    fonte_titulo = pygame.font.SysFont("arialblack", 96)
    fonte_msg    = pygame.font.SysFont("arial", 40, bold=True)
    fonte_botao  = pygame.font.SysFont("arial", 40, bold=False)

    titulo = fonte_titulo.render("PARABENS", True, (255, 225, 120))
    titulo_rect = titulo.get_rect(center=(LARGURA // 2, ALTURA // 2 - 130))

    msg = fonte_msg.render("Voce conquistou o ceu!", True, (235, 235, 255))
    msg_rect = msg.get_rect(center=(LARGURA // 2, ALTURA // 2 - 30))

    texto_jogar = fonte_botao.render("Jogar de Novo", True, (255, 255, 255))
    jogar_rect = texto_jogar.get_rect(center=(LARGURA // 2, ALTURA // 2 + 80))
    fundo_jogar = jogar_rect.inflate(60, 30)

    texto_sair = fonte_botao.render("Sair", True, (255, 255, 255))
    sair_rect = texto_sair.get_rect(center=(LARGURA // 2, ALTURA // 2 + 190))
    fundo_sair = sair_rect.inflate(60, 30)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if fundo_jogar.collidepoint(event.pos):
                    return
                if fundo_sair.collidepoint(event.pos):
                    pygame.quit()
                    exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    return
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    exit()

        mouse = pygame.mouse.get_pos()
        hover_jogar = fundo_jogar.collidepoint(mouse)
        hover_sair  = fundo_sair.collidepoint(mouse)

        screen.fill((18, 22, 45))
        screen.blit(titulo, titulo_rect)
        screen.blit(msg, msg_rect)
        pygame.draw.rect(screen, (80, 110, 190) if hover_jogar else (50, 70, 130), fundo_jogar, border_radius=10)
        pygame.draw.rect(screen, (200, 215, 255), fundo_jogar, 3, border_radius=10)
        screen.blit(texto_jogar, jogar_rect)
        pygame.draw.rect(screen, (80, 110, 190) if hover_sair else (50, 70, 130), fundo_sair, border_radius=10)
        pygame.draw.rect(screen, (200, 215, 255), fundo_sair, 3, border_radius=10)
        screen.blit(texto_sair, sair_rect)

        pygame.display.update()
        clock.tick(FPS)


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            reiniciar_jogo()

    screen.fill((0, 0, 0))
    all_sprites_group.update()
    spawner.update()

    venceu = False
    for bullet in bullet_group:
        for inimigo in pygame.sprite.spritecollide(bullet, enemy_group, False):
            morreu = inimigo.levar_dano(bullet.damage)
            bullet.kill()
            if morreu:
                player.moedas += inimigo.moedas
                if isinstance(inimigo, Boss):
                    venceu = True
                else:
                    spawner.registrar_kill(inimigo)

    if venceu:
        tela_vitoria()
        reiniciar_jogo()
        continue

    for item in item_group:
        if player.hitbox_rect.colliderect(item.rect):
            player.tem_chave = True
            item.kill()

    centro_player = pygame.math.Vector2(player.hitbox_rect.center)
    for inimigo in enemy_group:
        if inimigo.ataque_cooldown == 0:
            dist = (centro_player - pygame.math.Vector2(inimigo.rect.center)).magnitude()
            if dist <= inimigo.alcance + ATAQUE_MARGEM:
                inimigo.atacar()
                inimigo.ataque_cooldown = inimigo.ataque_delay
                if player.dano_cooldown == 0:
                    player.health -= inimigo.dano
                    player.dano_cooldown = ENEMY_DANO_COOLDOWN

    for tiro in enemy_bullet_group:
        if player.hitbox_rect.colliderect(tiro.rect):
            if player.dano_cooldown == 0:
                player.health -= tiro.dano
                player.dano_cooldown = ENEMY_DANO_COOLDOWN
            tiro.kill()

    if player.health <= 0:
        tela_game_over()
        reiniciar_jogo()
        continue

    camera.custom_draw()

    desenhar_barra_vida(screen, 20, 20, 200, 22, player.health, player.max_health)

    screen.blit(fonte_hud.render(f"Moedas: {player.moedas}", True, (255, 220, 80)), (20, 52))
    falta = max(0, KILLS_PARA_CHAVE - spawner.kills)
    if player.tem_chave:
        texto_chave = fonte_hud.render("Chave: OK (portal liberado)", True, (120, 230, 120))
    elif spawner.chave_dropada:
        texto_chave = fonte_hud.render("Chave dropada! Pegue-a", True, (245, 215, 60))
    else:
        texto_chave = fonte_hud.render(f"Chave: faltam {falta} inimigos", True, (220, 220, 220))
    screen.blit(texto_chave, (20, 82))

    if player.no_portal and not player.tem_chave:
        aviso = fonte_hud.render("Voce precisa da chave pra usar o portal!", True, (255, 120, 120))
        screen.blit(aviso, aviso.get_rect(center=(LARGURA // 2, ALTURA - 60)))

    dica = fonte_pequena.render("R reinicia o jogo", True, (220, 220, 220))
    screen.blit(dica, (LARGURA - dica.get_width() - 14, ALTURA - dica.get_height() - 10))

    for inimigo in enemy_group:
        bx = inimigo.rect.centerx - camera.offset.x - 25
        by = inimigo.rect.top     - camera.offset.y - 12
        desenhar_barra_vida(screen, bx, by, 50, 7, inimigo.health, inimigo.max_health)


    pygame.display.update()
    clock.tick(FPS)