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

# Mapa

TILE_SIZE = 16                   # tamanho do tile na imagem
TILE = TILE_SIZE * TILE_SCALE    # tamanho do tile na tela

# Teleporte / segundo mapa
TELEPORTE_ID = 99            # tile que funciona como portal (existe nos dois mapas)
TELEPORTE_MAPA1_POS = None    # (col, linha) fixa, ou None pra calcular pelo canto
TELEPORTE_MAPA1_CANTO = "superior-esquerdo"
MAPA2_COLUNAS, MAPA2_LINHAS = 30, 20
MAPA2_PISO = 18

# tiles onde dá pra pisar; o resto é parede
WALKABLE = {18, 27, 69, 70, 71, TELEPORTE_ID}

def carregar_tileset(nome, tile_px=TILE_SIZE):
    """Carrega um tileset. Procura na pasta do jogo e, se não achar, uma pasta acima."""
    for base in (BASE_DIR, os.path.dirname(BASE_DIR)):
        caminho = os.path.join(base, nome)
        if os.path.exists(caminho):
            img = pygame.image.load(caminho).convert_alpha()
            return img, img.get_width() // tile_px, tile_px
    raise FileNotFoundError(nome)

# mapa 1 usa um tileset só (16px). mapa 3 usa um pra cada camada (32px)
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
    """Todas as células andáveis a partir de (col, row)."""
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
    """Acha o tile andável mais perto do canto pedido, sem ficar preso atrás de parede."""
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
    """Desenho do portal, pra não depender de imagem."""
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    centro = (TILE // 2, TILE // 2)
    pygame.draw.circle(surf, (60, 20, 90),    centro, TILE // 2)
    pygame.draw.circle(surf, (150, 70, 230),  centro, TILE // 2 - 3)
    pygame.draw.circle(surf, (225, 190, 255), centro, TILE // 4)
    return surf


# Carrega os dois mapas
mapa_csv = carregar_csv(os.path.join(BASE_DIR, "mapa 1.csv"))

# se o CSV não tiver o portal, gente coloca um
start_col = int(PLAYER_START_X // TILE)
start_row = int(PLAYER_START_Y // TILE)
if achar_tile(mapa_csv, TELEPORTE_ID) is None:
    if TELEPORTE_MAPA1_POS:
        pos = TELEPORTE_MAPA1_POS
    else:
        pos = posicao_portal_canto(mapa_csv, start_col, start_row, TELEPORTE_MAPA1_CANTO)
    if pos:
        mapa_csv[pos[1]][pos[0]] = TELEPORTE_ID

# mapa 3: chão, parede e objetos em CSVs separados. o vazio andável é -1
chao2 = carregar_csv(os.path.join(BASE_DIR, "mapa 3_chao.csv"))
mapa2 = carregar_csv(os.path.join(BASE_DIR, "mapa 3_parede.csv"))
obj_path = os.path.join(BASE_DIR, "mapa 3_obj.csv")
obj2 = carregar_csv(obj_path) if os.path.exists(obj_path) else None
mapa2[len(mapa2) // 2][len(mapa2[0]) // 2] = TELEPORTE_ID
WALKABLE2 = {-1, TELEPORTE_ID}

PORTAL_SURF = surface_teleporte()

# tudo que muda de mapa fica em listas (índice = qual mapa)
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


# objetos são só visuais, não colidem
hitboxes_mapas = [gerar_hitboxes(m, w) for m, w in zip(mapas, walkables_mapas)]


class Mundo:
    """Guarda o mapa ativo (colisão, chão, tilesets, tamanho). Trocar de mapa
    é só mexer nos atributos daqui."""
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
    # chão primeiro, parede por cima. objetos são desenhados depois, na câmera
    if chao is not None:
        desenhar_camada(surface, chao, offset, ts_chao)
    desenhar_camada(surface, mapa, offset, ts_principal)

# Animação

IDLE_FRAMES = 16
WALK_FRAMES = 16
ATTACK_FRAMES = 16
ANIM_SPEED = 0.15

def carregar_animacao(nome_arquivo, num_frames, escala, colunas=1, linhas=1, fallback="hero.png"):
    """Recorta uma sprite sheet em grade (colunas x linhas), lendo os frames
    da esquerda pra direita e de cima pra baixo."""
    caminho = os.path.join(BASE_DIR, nome_arquivo)

    if os.path.exists(caminho):
        sheet = pygame.image.load(caminho).convert_alpha()
        largura_frame = sheet.get_width() // colunas
        altura_frame  = sheet.get_height() // linhas
        frames = []
        contagem = 0
        for linha in range(linhas):
            for coluna in range(colunas):
                if contagem >= num_frames:
                    break
                frame = pygame.Surface((largura_frame, altura_frame), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0),
                           pygame.Rect(coluna * largura_frame, linha * altura_frame,
                                       largura_frame, altura_frame))
                frames.append(pygame.transform.rotozoom(frame, 0, escala))
                contagem += 1
        return frames

    # sem sprite sheet ainda, usa uma imagem só
    img = pygame.image.load(os.path.join(BASE_DIR, fallback)).convert_alpha()
    return [pygame.transform.rotozoom(img, 0, escala)]

def normalizar_frames(animations):
    # mesmo tamanho de canvas em todo frame, senão o boneco pula ao trocar de animação
    maxw = max(f.get_width()  for frames in animations.values() for f in frames)
    maxh = max(f.get_height() for frames in animations.values() for f in frames)
    for estado, frames in animations.items():
        novos = []
        for f in frames:
            canvas = pygame.Surface((maxw, maxh), pygame.SRCALPHA)
            canvas.blit(f, ((maxw - f.get_width())  // 2,
                            (maxh - f.get_height()) // 2))
            novos.append(canvas)
        animations[estado] = novos
    return animations

# Sprites

all_sprites_group  = pygame.sprite.Group()
bullet_group       = pygame.sprite.Group()
enemy_group        = pygame.sprite.Group()
enemy_bullet_group = pygame.sprite.Group()
item_group         = pygame.sprite.Group()

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()

        self.animations = {
            'idle':   carregar_animacao('Idle_Shadowless.png',      IDLE_FRAMES,   PLAYER_SIZE, colunas=4, linhas=4),
            'walk':   carregar_animacao('Walk_Shadowless.png',      WALK_FRAMES,   PLAYER_SIZE, colunas=4, linhas=4),
            'attack': carregar_animacao('CastSpell_Shadowless.png', ATTACK_FRAMES, PLAYER_SIZE, colunas=4, linhas=4),
        }
        self.animations = normalizar_frames(self.animations)

        self.state        = 'idle'
        self.frame_index  = 0.0
        self.attacking    = False
        self.angle        = 0
        self.facing_left  = False

        self.base_player_image = self.animations['idle'][0]
        self.image = self.base_player_image

        self.pos = pygame.math.Vector2(PLAYER_START_X, PLAYER_START_Y)
        self.hitbox_rect = pygame.Rect(0, 0, 40, 52)   # hitbox menor que o sprite
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

        # vira o boneco pro lado do mouse
        if self.x_change_mouse_player < -1:
            self.facing_left = True
        elif self.x_change_mouse_player > 1:
            self.facing_left = False

        if self.facing_left:
            self.image = pygame.transform.flip(self.base_player_image, True, False)
        else:
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

        # normaliza a diagonal
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
        animation = self.animations[self.state]

        self.frame_index += ANIM_SPEED
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
        """Depois de teleportar, tira o player de dentro de qualquer parede."""
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
        """Se o player estiver em cima do portal, troca de mapa (com a chave)."""
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


# Inimigos: stats e spawn. todos atravessam parede e caçam o player em linha reta
NECRO_POS = (400, 400)
NEC_VIDA,   NEC_DANO,   NEC_ATAQUE   = 5,  1, 45
FRACO_VIDA, FRACO_DANO, FRACO_ATAQUE = 2,  1, 90
MIN_VIDA,   MIN_DANO,   MIN_ATAQUE   = 4,  1, 55
BOSS_VIDA,  BOSS_DANO,  BOSS_ATAQUE  = 40, 1, 40   # boss é esponja de bala

FRACO_SPEED = 3
BOSS_SPEED  = 2

FRACO_MOEDAS, MIN_MOEDAS, BOSS_MOEDAS = 1, 2, 10

# matar N inimigos dropa a chave, que libera o portal
KILLS_PARA_CHAVE  = 5
COOLDOWN_POS_META = 6000
MAX_VIVOS         = 4

SPAWN_FRACO_INTERVALO  = 4000
SPAWN_MINION_INTERVALO = 2500
BOSS_DELAY             = 12000
AVISO_DURACAO          = 800
SPAWN_GRACA            = 4000


def surface_boss_placeholder():
    """Boss anjo sombrio, desenhado direto no Pygame (sem depender de imagem)."""
    largura, altura = 100, 130
    surf = pygame.Surface((largura, altura), pygame.SRCALPHA)
    cx = largura // 2

    # asas
    asa_esq = [(cx, 40), (cx-45, 20), (cx-35, 45), (cx-50, 55), (cx-30, 65), (cx-40, 80), (cx-15, 70)]
    asa_dir = [(cx, 40), (cx+45, 20), (cx+35, 45), (cx+50, 55), (cx+30, 65), (cx+40, 80), (cx+15, 70)]
    pygame.draw.polygon(surf, (43, 34, 51), asa_esq)
    pygame.draw.polygon(surf, (43, 34, 51), asa_dir)

    # veste
    veste = [(cx, 45), (cx-25, 75), (cx-32, 125), (cx+32, 125), (cx+25, 75)]
    pygame.draw.polygon(surf, (28, 22, 38), veste)

    # capuz
    capuz = [(cx, 15), (cx-20, 20), (cx-16, 45), (cx+16, 45), (cx+20, 20)]
    pygame.draw.polygon(surf, (36, 27, 48), capuz)

    # cabeça
    pygame.draw.circle(surf, (232, 217, 200), (cx, 32), 15)

    # halo
    pygame.draw.ellipse(surf, (201, 168, 255), (cx-17, 8, 34, 10), 3)

    # olhos
    pygame.draw.circle(surf, (201, 168, 255), (cx-6, 32), 2)
    pygame.draw.circle(surf, (201, 168, 255), (cx+6, 32), 2)

    return surf


BOSS_SURF = surface_boss_placeholder()

# tiro do boss
BOSS_TIRO_INTERVALO  = 2000
BOSS_TIRO_DANO       = 3
BOSS_BULLET_SPEED    = 7
BOSS_BULLET_LIFETIME = 4000


def surface_boss_bullet():
    """Tiro do boss: bola laranja."""
    r = 14
    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 120, 40),  (r, r), r)
    pygame.draw.circle(surf, (255, 225, 130), (r, r), r // 2)
    return surf


BOSS_BULLET_SURF = surface_boss_bullet()


def posicao_spawn(mapa_indice, dist_min_tiles=6):
    """Sorteia um tile andável, longe do player, pra nascer um inimigo."""
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
                 escala=2, imagem='0.png', ataque_delay=45, moedas=1):
        super().__init__(enemy_group, all_sprites_group)
        self.mapa = mapa
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
        dist = (pv - ev).magnitude()
        self.direction = (pv - ev).normalize() if dist > 0 else pygame.math.Vector2()
        self.position += self.direction * self.speed
        self.rect.center = (int(self.position.x), int(self.position.y))

    def levar_dano(self, dano):
        self.health -= dano
        if self.health <= 0:
            self.kill()
            return True
        return False

    def update(self):
        self.hunt_player()
        if self.ataque_cooldown > 0:
            self.ataque_cooldown -= 1


class Boss(Enemy):
    """Boss do mapa 3, usa BOSS_SURF (anjo desenhado, sem imagem)."""
    def __init__(self, position, mapa):
        pygame.sprite.Sprite.__init__(self, enemy_group, all_sprites_group)
        self.mapa = mapa
        self.image = BOSS_SURF
        self.rect  = self.image.get_rect(center=position)
        self.position  = pygame.math.Vector2(position)
        self.direction = pygame.math.Vector2()
        self.speed = BOSS_SPEED
        self.max_health = BOSS_VIDA
        self.health = BOSS_VIDA
        self.dano = BOSS_DANO
        self.moedas = BOSS_MOEDAS
        self.ataque_delay = BOSS_ATAQUE
        self.ataque_cooldown = 0
        self.ultimo_tiro = pygame.time.get_ticks()

    def atirar(self):
        EnemyBullet(self.rect.centerx, self.rect.centery,
                    player.hitbox_rect.center, BOSS_TIRO_DANO)

    def update(self):
        super().update()
        agora = pygame.time.get_ticks()
        if agora - self.ultimo_tiro >= BOSS_TIRO_INTERVALO:
            self.atirar()
            self.ultimo_tiro = agora


class EnemyBullet(pygame.sprite.Sprite):
    """Tiro do boss: vai na direção do player."""
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


def surface_chave():
    """Chave amarela simples."""
    surf = pygame.Surface((30, 30), pygame.SRCALPHA)
    pygame.draw.circle(surf, (245, 215, 60), (10, 10), 8)
    pygame.draw.circle(surf, (120, 90, 10),  (10, 10), 8, 2)
    pygame.draw.rect(surf, (245, 215, 60), (13, 10, 4, 17))
    pygame.draw.rect(surf, (245, 215, 60), (17, 21, 6, 4))
    return surf


CHAVE_SURF = surface_chave()


class Chave(pygame.sprite.Sprite):
    """Chave que o 5o inimigo dropa. Libera o portal ao pegar."""
    def __init__(self, position):
        super().__init__(item_group, all_sprites_group)
        self.image = CHAVE_SURF
        self.rect  = self.image.get_rect(center=position)


class Camera(pygame.sprite.Group):
    def __init__(self):
        super().__init__()
        self.offset = pygame.math.Vector2()

    def custom_draw(self):
        self.offset.x = player.rect.centerx - LARGURA // 2
        self.offset.y = player.rect.centery  - ALTURA  // 2

        # trava a câmera nas bordas do mapa
        self.offset.x = max(0, min(self.offset.x, mundo.largura - LARGURA))
        self.offset.y = max(0, min(self.offset.y, mundo.altura  - ALTURA))

        desenhar_mapa(screen, mundo.chao, mundo.mapa, self.offset,
                      mundo.ts_chao, mundo.ts_principal)

        spawner.desenhar_avisos(screen, self.offset)

        for sprite in all_sprites_group:
            screen.blit(sprite.image, sprite.rect.topleft - self.offset)

        # objetos ficam por cima do personagem
        if mundo.obj is not None:
            desenhar_camada(screen, mundo.obj, self.offset, mundo.ts_obj)


class GerenciadorSpawn:
    """Cria os inimigos aos poucos, conforme o mapa ativo."""
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
        """Conta o kill e, no 5o, dropa a chave e dá uma folga sem spawn."""
        self.kills += 1
        if not self.chave_dropada and self.kills >= KILLS_PARA_CHAVE:
            Chave(inimigo.rect.center)
            self.chave_dropada = True
            self.pausa_ate = pygame.time.get_ticks() + COOLDOWN_POS_META

    def update(self):
        agora = pygame.time.get_ticks()

        # aviso que já encheu: nasce o inimigo
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
                                    velocidade=FRACO_SPEED, escala=1.3,
                                    ataque_delay=FRACO_ATAQUE, moedas=FRACO_MOEDAS),
                    TILE // 2)
                self.ultimo = agora
        elif self.mapa == 1:
            if agora - self.ultimo >= SPAWN_MINION_INTERVALO:
                self.agendar(
                    posicao_spawn(1),
                    lambda p: Enemy(p, mapa=1, vida=MIN_VIDA, dano=MIN_DANO,
                                    velocidade=ENEMY_SPEED, escala=2,
                                    ataque_delay=MIN_ATAQUE, moedas=MIN_MOEDAS),
                    TILE // 2)
                self.ultimo = agora
            if not self.boss_criado and agora - self.inicio >= BOSS_DELAY:
                self.agendar(
                    posicao_spawn(1, dist_min_tiles=8),
                    lambda p: Boss(p, mapa=1),
                    70)
                self.boss_criado = True

    def desenhar_avisos(self, surface, offset):
        """Círculo de aviso: fica mais cheio conforme perto de nascer o inimigo."""
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
    """Barra de vida: fundo vermelho + parte verde proporcional."""
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
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
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


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    screen.fill((0, 0, 0))
    all_sprites_group.update()
    spawner.update()

    # bala acerta inimigo -> tira vida, e se morrer dá moeda e conta o kill
    for bullet in bullet_group:
        for inimigo in pygame.sprite.spritecollide(bullet, enemy_group, False):
            morreu = inimigo.levar_dano(bullet.damage)
            bullet.kill()
            if morreu:
                player.moedas += inimigo.moedas
                spawner.registrar_kill(inimigo)

    # player pega a chave -> libera o portal
    for item in item_group:
        if player.hitbox_rect.colliderect(item.rect):
            player.tem_chave = True
            item.kill()

    # inimigo encosta no player -> tira vida
    if player.dano_cooldown == 0:
        for inimigo in enemy_group:
            if inimigo.ataque_cooldown == 0 and player.hitbox_rect.colliderect(inimigo.rect):
                player.health -= inimigo.dano
                player.dano_cooldown = ENEMY_DANO_COOLDOWN
                inimigo.ataque_cooldown = inimigo.ataque_delay
                break

    # tiro do boss acerta o player
    for tiro in enemy_bullet_group:
        if player.hitbox_rect.colliderect(tiro.rect):
            if player.dano_cooldown == 0:
                player.health -= tiro.dano
                player.dano_cooldown = ENEMY_DANO_COOLDOWN
            tiro.kill()

    # vida zerou -> game over
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

    # barra de vida flutuando acima de cada inimigo
    for inimigo in enemy_group:
        bx = inimigo.rect.centerx - camera.offset.x - 25
        by = inimigo.rect.top     - camera.offset.y - 12
        desenhar_barra_vida(screen, bx, by, 50, 7, inimigo.health, inimigo.max_health)

    # debug — descomenta pra ver as hitboxes
    # for box in mundo.hitboxes:
    #     pos = (box.x - camera.offset.x, box.y - camera.offset.y, box.width, box.height)
    #     pygame.draw.rect(screen, (255, 0, 0), pos, 1)

    pygame.display.update()
    clock.tick(FPS)
