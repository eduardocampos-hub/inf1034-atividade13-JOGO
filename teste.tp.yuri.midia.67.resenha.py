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

TILE_SIZE = 16                   # tamanho do tile dentro da imagem
TILE = TILE_SIZE * TILE_SCALE    # tamanho do tile na tela

# ── TELEPORTE / SEGUNDO MAPA ──────────────────────────────────────────────────
TELEPORTE_ID = 99            # tile que funciona como portal (fica nos DOIS mapas)
# Onde fica o portal no mapa 1:
#   - TELEPORTE_MAPA1_POS = (col, linha) -> posicao EXATA (tem prioridade)
#   - senao usa o canto abaixo, no tile pisavel mais perto do canto que dah
#     pra alcancar andando (nunca fica preso atras de parede).
TELEPORTE_MAPA1_POS = None
TELEPORTE_MAPA1_CANTO = "superior-esquerdo"   # superior-esquerdo / superior-direito /
                                              # inferior-esquerdo / inferior-direito
MAPA2_COLUNAS, MAPA2_LINHAS = 30, 20   # tamanho do mapa plano
MAPA2_PISO = 18                        # tile de chao do mapa plano

# tiles onde dá pra pisar; o resto vira parede (o portal tambem precisa ser pisavel)
WALKABLE = {18, 27, 69, 70, 71, TELEPORTE_ID}

def carregar_tileset(nome, tile_px=TILE_SIZE):
    """Carrega um tileset e devolve (imagem, num_colunas, tile_px).
    tile_px = tamanho do tile DENTRO da imagem (origem; o tileset.png tem 16,
    os TX Tileset tem 32). Procura na pasta do jogo e, se nao achar, no Desktop."""
    for base in (BASE_DIR, os.path.dirname(BASE_DIR)):
        caminho = os.path.join(base, nome)
        if os.path.exists(caminho):
            img = pygame.image.load(caminho).convert_alpha()
            return img, img.get_width() // tile_px, tile_px
    raise FileNotFoundError(nome)

# Mapa 1 usa um tileset so (16px). O mapa 3 usa um por camada, ambos de 32px:
# chao = Grass, parede = Wall.
TS_MAPA1 = carregar_tileset("tileset.png")                  # tiles de 16px
TS_GRASS = carregar_tileset("TX Tileset Grass.png", 32)     # chao do mapa 3, 32px
TS_WALL  = carregar_tileset("TX Tileset Wall.png", 32)      # parede do mapa 3, 32px
TS_PLANT = carregar_tileset("TX Plant.png", 32)             # objetos do mapa 3, 32px

tileset_img, TILESET_COLUNAS, _ = TS_MAPA1                  # padrao do pegar_tile


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
    if tileset is None:                       # padrao: tileset do mapa 1 (16px)
        tileset, colunas, tile_px = tileset_img, TILESET_COLUNAS, TILE_SIZE
    indice = tile_id - 1
    coluna = indice % colunas
    linha  = indice // colunas
    area = pygame.Rect(coluna * tile_px, linha * tile_px, tile_px, tile_px)
    tile = tileset.subsurface(area)
    return pygame.transform.scale(tile, (TILE, TILE))   # escala pro tamanho da tela


def achar_tile(mapa, tile_id):
    """Primeira posicao (col, linha) onde aparece tile_id, ou None."""
    for y, linha in enumerate(mapa):
        for x, t in enumerate(linha):
            if t == tile_id:
                return (x, y)
    return None


def celulas_alcancaveis(mapa, col, row):
    """Todas as celulas pisaveis que dah pra alcancar ANDANDO a partir de (col,row)."""
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
    """Tile pisavel mais perto do CANTO pedido, mas so entre os alcancaveis a pe
    a partir do spawn (assim o portal nunca cai preso atras de parede)."""
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
    reg.discard((spawn_col, spawn_row))   # nao nascer em cima do player
    if not reg:
        return None
    return min(reg, key=lambda c: abs(c[0] - alvo[0]) + abs(c[1] - alvo[1]))


def surface_teleporte():
    """Desenho proprio do portal (nao depende do tileset), pra ser sempre visivel."""
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    centro = (TILE // 2, TILE // 2)
    pygame.draw.circle(surf, (60, 20, 90),    centro, TILE // 2)
    pygame.draw.circle(surf, (150, 70, 230),  centro, TILE // 2 - 3)
    pygame.draw.circle(surf, (225, 190, 255), centro, TILE // 4)
    return surf


# ── CARREGA OS DOIS MAPAS ──────────────────────────────────────────────────────
mapa_csv = carregar_csv(os.path.join(BASE_DIR, "mapa 1.csv"))

# Coloca o portal (99) no mapa 1 se ele ainda nao existir no CSV.
# Se voce ja por o 99 no editor, ele usa o seu.
start_col = int(PLAYER_START_X // TILE)
start_row = int(PLAYER_START_Y // TILE)
if achar_tile(mapa_csv, TELEPORTE_ID) is None:
    if TELEPORTE_MAPA1_POS:
        pos = TELEPORTE_MAPA1_POS
    else:
        pos = posicao_portal_canto(mapa_csv, start_col, start_row, TELEPORTE_MAPA1_CANTO)
    if pos:
        mapa_csv[pos[1]][pos[0]] = TELEPORTE_ID

# Segundo mapa: o MAPA 3 (o que voce criou), em tres camadas de CSV:
# chao por baixo, parede no meio (colisao + desenhada por cima) e objetos por cima.
# 'mapa2' eh a camada de PAREDE; 'chao2' eh o piso; 'obj2' os objetos (opcional).
# O vazio andavel do mapa 3 eh -1; o resto vira parede.
chao2 = carregar_csv(os.path.join(BASE_DIR, "mapa 3_chao.csv"))
mapa2 = carregar_csv(os.path.join(BASE_DIR, "mapa 3_parede.csv"))
obj_path = os.path.join(BASE_DIR, "mapa 3_obj.csv")
obj2 = carregar_csv(obj_path) if os.path.exists(obj_path) else None
mapa2[len(mapa2) // 2][len(mapa2[0]) // 2] = TELEPORTE_ID
WALKABLE2 = {-1, TELEPORTE_ID}

PORTAL_SURF = surface_teleporte()   # usado pelo desenhar_mapa

# Tudo que muda quando troca de mapa fica em listas (indice = qual mapa).
mapas            = [mapa_csv, mapa2]                 # camada de colisao/topo (parede)
chaos            = [None, chao2]                     # camada de piso (ou None)
objs             = [None, obj2]                      # camada de objetos (ou None)
walkables_mapas  = [WALKABLE, WALKABLE2]             # o que eh andavel em cada um
# tileset (imagem, colunas, tile_px) de cada CAMADA. Mapa 1 so tem a principal.
ts_principal_mapas = [TS_MAPA1, TS_WALL]             # tileset da parede/topo
ts_chao_mapas      = [None,     TS_GRASS]            # tileset do piso (ou None)
ts_obj_mapas       = [None,     TS_PLANT]            # tileset dos objetos (ou None)
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


# Objetos (camada obj) sao so visuais: NAO entram na colisao, so a parede entra.
hitboxes_mapas = [gerar_hitboxes(m, w) for m, w in zip(mapas, walkables_mapas)]


class Mundo:
    """Guarda o estado do mapa ATIVO (mapa, chao, hitboxes, tilesets, tamanho).
    Trocar de mapa = so mexer nos atributos deste objeto; por isso o resto do
    codigo nao precisa de 'global', ele le sempre 'mundo.algo'."""
    def __init__(self, indice=0):
        self.ir_para(indice)

    def ir_para(self, indice):
        self.indice  = indice
        self.mapa = mapas[indice]            # camada de colisao/topo (parede)
        self.chao = chaos[indice]            # camada de piso (ou None)
        self.obj = objs[indice]              # camada de objetos (ou None)
        self.hitboxes = hitboxes_mapas[indice]
        self.ts_principal = ts_principal_mapas[indice]
        self.ts_chao = ts_chao_mapas[indice]
        self.ts_obj = ts_obj_mapas[indice]
        self.largura = mapw_mapas[indice]       # a camera usa pra travar nas bordas
        self.altura = maph_mapas[indice]
        self.teleporte = teleportes_mapas[indice]

mundo = Mundo(0)


def trocar_mapa():
    mundo.ir_para(1 - mundo.indice)        # alterna entre 0 e 1
    col, row = mundo.teleporte
    player.pos.x = col * TILE + TILE // 2
    player.pos.y = row * TILE + TILE // 2
    player.hitbox_rect.center = (int(player.pos.x), int(player.pos.y))
    player.rect.center = player.hitbox_rect.center
    player.desencostar_paredes()   # nao deixa o player nascer preso numa parede
    spawner.iniciar(mundo.indice)  # zera e recomeca o spawn de inimigos do novo mapa


def desenhar_camada(surface, mapa, offset, ts):
    tileset, colunas, tile_px = ts          # ts = (imagem, num_colunas, tile_px)
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            tile_id = mapa[y][x]
            if tile_id <= 0:
                continue
            if tile_id == TELEPORTE_ID:
                tile = PORTAL_SURF          # o portal tem desenho proprio
            else:
                tile = pegar_tile(tile_id, tileset, colunas, tile_px)
            surface.blit(tile, (x * TILE - offset.x, y * TILE - offset.y))


def desenhar_mapa(surface, chao, mapa, offset, ts_chao, ts_principal):
    # camadas DEBAIXO do personagem: chao (Grass) por baixo, parede (Wall) por cima.
    # Os objetos (plantas) sao desenhados depois dos sprites, na camera.
    if chao is not None:
        desenhar_camada(surface, chao, offset, ts_chao)
    desenhar_camada(surface, mapa, offset, ts_principal)

# Animação

IDLE_FRAMES = 6    # Idle.png → 6 frames
WALK_FRAMES = 8    # Run.png  → 8 frames
ATTACK_FRAMES = 4    # Hit.png  → 4 frames
ANIM_SPEED = 0.15

def carregar_animacao(nome_arquivo, num_frames, escala, fallback="hero.png"):
    caminho = os.path.join(BASE_DIR, nome_arquivo)

    if os.path.exists(caminho):
        sheet = pygame.image.load(caminho).convert_alpha()
        largura_frame = sheet.get_width() // num_frames
        altura_frame  = sheet.get_height()
        frames = []
        for i in range(num_frames):
            frame = pygame.Surface((largura_frame, altura_frame), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0),
                       pygame.Rect(i * largura_frame, 0, largura_frame, altura_frame))
            frames.append(pygame.transform.rotozoom(frame, 0, escala))
        return frames

    # fallback enquanto não há sprite sheet
    img = pygame.image.load(os.path.join(BASE_DIR, fallback)).convert_alpha()
    return [pygame.transform.rotozoom(img, 0, escala)]

def normalizar_frames(animations):
    # mesmo tamanho de canvas em todos os frames, senão o boneco "pula" ao trocar de animação
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
bullet_group       = pygame.sprite.Group()   # balas do player (acertam inimigos)
enemy_group        = pygame.sprite.Group()
enemy_bullet_group = pygame.sprite.Group()   # tiros do boss (acertam o player)
item_group         = pygame.sprite.Group()   # itens no chao (ex: a chave do portal)

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()

        self.animations = {
            'idle':   carregar_animacao('Idle.png', IDLE_FRAMES,   PLAYER_SIZE),
            'walk':   carregar_animacao('Run.png',  WALK_FRAMES,   PLAYER_SIZE),
            'attack': carregar_animacao('Hit.png',  ATTACK_FRAMES, PLAYER_SIZE),
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
        # hitbox menor que o sprite (só o corpo), pra passar pelos corredores
        self.hitbox_rect = pygame.Rect(0, 0, 40, 52)
        self.hitbox_rect.center = self.pos
        self.rect = self.hitbox_rect.copy()

        self.shoot = False
        self.speed = PLAYER_SPEED
        self.shot_cooldown = 0
        self.gun_barrel_offset = pygame.math.Vector2(GUN_OFFSET_X, GUNOFFSET_Y)

        self.acabou_de_teleportar = False   # trava p/ nao teleportar em loop

        self.max_health = 10       # vida maxima do personagem principal (a barra escala sozinha)
        self.health = self.max_health
        self.dano_cooldown = 0     # invencibilidade temporaria apos tomar dano

        self.moedas = 0            # ganha moedas ao matar inimigos
        self.tem_chave = False     # so pode usar o portal com a chave na mao
        self.no_portal = False     # esta pisando no portal agora? (pro aviso do HUD)

    def player_aim(self):
        self.mouse_coords = pygame.mouse.get_pos()
        self.x_change_mouse_player = self.mouse_coords[0] - LARGURA // 2
        self.y_change_mouse_player = self.mouse_coords[1] - ALTURA  // 2
        self.angle = math.degrees(
            math.atan2(self.y_change_mouse_player, self.x_change_mouse_player))

        # espelha o boneco pro lado do mouse; a zona morta no centro evita o tremido
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

        # normaliza a diagonal pra não andar mais rápido na diagonal
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
                self.attacking = False   # acabou o golpe, volta pro idle/walk

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
        """Apos teleportar, empurra o player pra fora de qualquer parede pelo
        MENOR caminho. Sem isso, cair colado numa parede (ex: portal no canto)
        faz a move() empurrar o player em cascata pra fora do mapa."""
        for box in mundo.hitboxes:
            if self.hitbox_rect.colliderect(box):
                dx_esq   = box.right - self.hitbox_rect.left      # empurrar pra direita
                dx_dir   = self.hitbox_rect.right - box.left      # empurrar pra esquerda
                dy_cima  = box.bottom - self.hitbox_rect.top      # empurrar pra baixo
                dy_baixo = self.hitbox_rect.bottom - box.top      # empurrar pra cima
                menor = min(dx_esq, dx_dir, dy_cima, dy_baixo)
                if   menor == dy_cima:  self.hitbox_rect.top    = box.bottom
                elif menor == dy_baixo: self.hitbox_rect.bottom = box.top
                elif menor == dx_esq:   self.hitbox_rect.left   = box.right
                else:                   self.hitbox_rect.right  = box.left
        self.pos.x = self.hitbox_rect.centerx
        self.pos.y = self.hitbox_rect.centery
        self.rect.center = self.hitbox_rect.center

    def checar_teleporte(self):
        """Ve em qual tile o player esta. Se for o portal, troca de mapa.
        A trava impede teleportar em loop ao cair em cima do portal do outro
        mapa: so libera de novo quando o player sai de cima dele."""
        col = self.hitbox_rect.centerx // TILE
        row = self.hitbox_rect.centery // TILE
        em_cima = (0 <= row < len(mundo.mapa) and 0 <= col < len(mundo.mapa[row])
                   and mundo.mapa[row][col] == TELEPORTE_ID)
        self.no_portal = em_cima

        if em_cima:
            # so teleporta com a chave (que o 5o inimigo dropa)
            if self.tem_chave and not self.acabou_de_teleportar:
                trocar_mapa()
                self.acabou_de_teleportar = True
        else:
            self.acabou_de_teleportar = False

    def update(self):
        self.user_input()
        self.move()
        self.checar_teleporte()   # troca de mapa ao pisar no portal
        self.set_state()
        self.animate()
        self.player_aim()
        if self.shot_cooldown > 0:
            self.shot_cooldown -= 1
        if self.dano_cooldown > 0:      # invencibilidade temporaria apos tomar dano
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
        self.damage = 1                 # dano que a bala causa no inimigo

    def update(self):
        self.x += self.x_vel
        self.y += self.y_vel
        self.rect.center = (int(self.x), int(self.y))
        if pygame.time.get_ticks() - self.spawn_time > BULLET_LIFETIME:
            self.kill()


# ── INIMIGOS: stats e spawn ─────────────────────────────────────────────────────
# vida / dano / cadencia de ataque (em frames; 60 frames = 1s). Todos os inimigos
# atravessam parede e caçam o player em linha reta (nao tem pathfinding).
NECRO_POS = (400, 400)                              # onde o necromante nasce no mapa 1
NEC_VIDA,   NEC_DANO,   NEC_ATAQUE   = 5,  1, 45    # necromante (mapa 1)
FRACO_VIDA, FRACO_DANO, FRACO_ATAQUE = 2,  1, 90    # inimigo fraco (mapa 1): menos vida
                                                    # e ataca metade das vezes (menos dano)
MIN_VIDA,   MIN_DANO,   MIN_ATAQUE   = 4,  1, 55    # minions (mapa 3)
BOSS_VIDA,  BOSS_DANO,  BOSS_ATAQUE  = 40, 1, 40    # boss (mapa 3): muita vida (esponja de balas)

FRACO_SPEED = 3      # o fraco anda mais devagar que o necromante (ENEMY_SPEED = 4)
BOSS_SPEED  = 2      # o boss eh lento e pesado

# moedas que cada tipo de inimigo dropa ao morrer
FRACO_MOEDAS, MIN_MOEDAS, BOSS_MOEDAS = 1, 2, 10

# progressao do mapa: matar N inimigos -> o N-esimo dropa a chave -> libera o portal
KILLS_PARA_CHAVE  = 5      # quantos inimigos matar pra dropar a chave
COOLDOWN_POS_META = 6000   # ms de folga sem novos inimigos depois do 5o kill
MAX_VIVOS         = 4      # quantos inimigos podem existir ao mesmo tempo (nao floodar a tela)

# tempos de spawn em milissegundos (o spawn eh continuo; quem limita eh MAX_VIVOS)
SPAWN_FRACO_INTERVALO  = 4000    # mapa 1: tempo entre cada inimigo fraco
SPAWN_MINION_INTERVALO = 2500    # mapa 3: tempo entre cada minion
BOSS_DELAY             = 12000   # mapa 3: tempo ate o boss aparecer
AVISO_DURACAO          = 800     # ms que o circulo de aviso fica no chao antes do inimigo nascer
SPAWN_GRACA            = 4000    # ms de "paz" no comeco de cada mapa (nada nasce) pro player se ambientar


def surface_boss_placeholder():
    """Boss provisorio: so um retangulo preto ate ter a textura.
    Quando achar a imagem, troque por pygame.image.load(...) na classe Boss."""
    surf = pygame.Surface((100, 130))
    surf.fill((0, 0, 0))
    return surf


BOSS_SURF = surface_boss_placeholder()

# tiro do boss: nao muito frequente, mas doi mais que o inimigo normal (dano 1)
BOSS_TIRO_INTERVALO  = 2000   # ms entre um tiro e outro (2 segundos)
BOSS_TIRO_DANO       = 3      # dano do tiro do boss
BOSS_BULLET_SPEED    = 7      # velocidade do tiro
BOSS_BULLET_LIFETIME = 4000   # ms ate o tiro sumir sozinho


def surface_boss_bullet():
    """Placeholder do tiro do boss: uma bola laranja (troque por imagem se quiser)."""
    r = 14
    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 120, 40),  (r, r), r)
    pygame.draw.circle(surf, (255, 225, 130), (r, r), r // 2)
    return surf


BOSS_BULLET_SURF = surface_boss_bullet()


def posicao_spawn(mapa_indice, dist_min_tiles=6):
    """Sorteia um tile pisavel do mapa, longe do player, pra nascer um inimigo.
    (como os inimigos atravessam parede, so precisamos de um tile valido.)"""
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
        self.mapa = mapa                # em qual mapa este inimigo vive
        self.image = pygame.transform.rotozoom(
            pygame.image.load(imagem).convert_alpha(), 0, escala)
        self.rect  = self.image.get_rect(center=position)
        self.position  = pygame.math.Vector2(position)
        self.direction = pygame.math.Vector2()
        self.speed = velocidade
        self.max_health = vida          # vida maxima
        self.health = vida
        self.dano = dano                # quanto de vida tira do player ao encostar
        self.moedas = moedas            # moedas que solta ao morrer
        self.ataque_delay = ataque_delay  # frames de espera entre um ataque e outro
        self.ataque_cooldown = 0

    def hunt_player(self):
        pv = pygame.math.Vector2(player.hitbox_rect.center)
        ev = pygame.math.Vector2(self.rect.center)
        dist = (pv - ev).magnitude()
        self.direction = (pv - ev).normalize() if dist > 0 else pygame.math.Vector2()
        self.position += self.direction * self.speed
        self.rect.center = (int(self.position.x), int(self.position.y))

    def levar_dano(self, dano):         # tira vida e morre quando chega a 0
        self.health -= dano             # devolve True se morreu (pra dar moeda/contar kill)
        if self.health <= 0:
            self.kill()
            return True
        return False

    def update(self):
        self.hunt_player()
        if self.ataque_cooldown > 0:    # espera entre ataques (proprio de cada inimigo)
            self.ataque_cooldown -= 1


class Boss(Enemy):
    """Boss do mapa 3. Ainda sem textura: usa BOSS_SURF (placeholder desenhado)."""
    def __init__(self, position, mapa):
        # nao chama Enemy.__init__ pra nao tentar carregar imagem de arquivo
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
        self.ultimo_tiro = pygame.time.get_ticks()   # so atira 2s depois de nascer

    def atirar(self):
        # dispara um tiro na direcao de onde o player esta agora
        EnemyBullet(self.rect.centerx, self.rect.centery,
                    player.hitbox_rect.center, BOSS_TIRO_DANO)

    def update(self):
        super().update()   # caca o player + conta o cooldown do ataque corpo-a-corpo
        agora = pygame.time.get_ticks()
        if agora - self.ultimo_tiro >= BOSS_TIRO_INTERVALO:
            self.atirar()
            self.ultimo_tiro = agora


class EnemyBullet(pygame.sprite.Sprite):
    """Tiro do boss: vai na direcao do player e tira vida ao acertar."""
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
    """Placeholder da chave: um desenho simples amarelo (troque por imagem se quiser)."""
    surf = pygame.Surface((30, 30), pygame.SRCALPHA)
    pygame.draw.circle(surf, (245, 215, 60), (10, 10), 8)     # cabeca da chave
    pygame.draw.circle(surf, (120, 90, 10),  (10, 10), 8, 2)
    pygame.draw.rect(surf, (245, 215, 60), (13, 10, 4, 17))   # haste
    pygame.draw.rect(surf, (245, 215, 60), (17, 21, 6, 4))    # dente
    return surf


CHAVE_SURF = surface_chave()


class Chave(pygame.sprite.Sprite):
    """Chave dropada pelo 5o inimigo. Ao encostar nela, o portal fica liberado."""
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

        # trava a câmera nas bordas pra não mostrar o vazio fora do mapa
        self.offset.x = max(0, min(self.offset.x, mundo.largura - LARGURA))
        self.offset.y = max(0, min(self.offset.y, mundo.altura  - ALTURA))

        # camadas debaixo do personagem: chao + parede
        desenhar_mapa(screen, mundo.chao, mundo.mapa, self.offset,
                      mundo.ts_chao, mundo.ts_principal)

        # circulos de aviso no chao, embaixo de onde os inimigos vao nascer
        spawner.desenhar_avisos(screen, self.offset)

        # personagem e outros sprites
        for sprite in all_sprites_group:
            screen.blit(sprite.image, sprite.rect.topleft - self.offset)

        # objetos (plantas) POR CIMA do personagem: ele passa por tras delas
        if mundo.obj is not None:
            desenhar_camada(screen, mundo.obj, self.offset, mundo.ts_obj)


class GerenciadorSpawn:
    """Cria os inimigos aos poucos (com atraso) conforme o mapa ativo.
    Ao (re)iniciar um mapa, apaga os inimigos do mapa anterior e zera a contagem,
    assim cada mapa tem os seus inimigos e eles nao vazam de um pro outro."""
    def __init__(self):
        self.iniciar(mundo.indice)

    def iniciar(self, mapa_indice):
        for inimigo in list(enemy_group):      # limpa os inimigos do mapa anterior
            inimigo.kill()
        for tiro in list(enemy_bullet_group):  # e os tiros de boss que sobraram
            tiro.kill()
        for item in list(item_group):          # e a chave que sobrou do mapa anterior
            item.kill()
        self.mapa        = mapa_indice
        self.inicio      = pygame.time.get_ticks()
        self.ultimo      = self.inicio
        self.boss_criado = False
        self.avisos      = []                  # circulos de aviso ainda esperando pra nascer
        self.kills       = 0                   # quantos inimigos o player matou neste mapa
        self.chave_dropada = False             # ja soltou a chave deste mapa?
        self.pausa_ate   = 0                   # nao spawnar enquanto agora < pausa_ate
        player.tem_chave = False               # cada mapa exige matar 5 + pegar a chave de novo

    def agendar(self, pos, criar, raio):
        self.avisos.append({
            'pos':    pos,
            'raio':   raio,
            'quando': pygame.time.get_ticks() + AVISO_DURACAO,
            'criar':  criar,
        })

    def registrar_kill(self, inimigo):
        """Chamado quando um inimigo morre. Conta o kill e, no 5o, dropa a chave
        onde ele morreu e da um tempo de folga sem novos inimigos."""
        self.kills += 1
        if not self.chave_dropada and self.kills >= KILLS_PARA_CHAVE:
            Chave(inimigo.rect.center)                          # o 5o inimigo dropa a chave
            self.chave_dropada = True
            self.pausa_ate = pygame.time.get_ticks() + COOLDOWN_POS_META

    def update(self):
        agora = pygame.time.get_ticks()

        # 1) avisos que ja "encheram": nasce o inimigo no lugar do circulo
        for aviso in list(self.avisos):
            if agora >= aviso['quando']:
                aviso['criar'](aviso['pos'])
                self.avisos.remove(aviso)

        # espaco pro player se ambientar: nos primeiros SPAWN_GRACA ms nada nasce
        if agora - self.inicio < SPAWN_GRACA:
            return
        # cooldown depois do 5o kill: uma folga sem novos inimigos
        if agora < self.pausa_ate:
            return
        # nao floodar a tela: respeita um limite de inimigos vivos ao mesmo tempo
        if len(enemy_group) + len(self.avisos) >= MAX_VIVOS:
            return

        # 2) agenda novos spawns conforme o mapa
        if self.mapa == 0:
            # mapa 1: inimigos fracos, um a cada SPAWN_FRACO_INTERVALO ms
            if agora - self.ultimo >= SPAWN_FRACO_INTERVALO:
                self.agendar(
                    posicao_spawn(0),
                    lambda p: Enemy(p, mapa=0, vida=FRACO_VIDA, dano=FRACO_DANO,
                                    velocidade=FRACO_SPEED, escala=1.3,
                                    ataque_delay=FRACO_ATAQUE, moedas=FRACO_MOEDAS),
                    TILE // 2)
                self.ultimo = agora
        elif self.mapa == 1:
            # mapa 3: varios minions com atraso...
            if agora - self.ultimo >= SPAWN_MINION_INTERVALO:
                self.agendar(
                    posicao_spawn(1),
                    lambda p: Enemy(p, mapa=1, vida=MIN_VIDA, dano=MIN_DANO,
                                    velocidade=ENEMY_SPEED, escala=2,
                                    ataque_delay=MIN_ATAQUE, moedas=MIN_MOEDAS),
                    TILE // 2)
                self.ultimo = agora
            # ...e o boss depois de BOSS_DELAY ms (aviso maior)
            if not self.boss_criado and agora - self.inicio >= BOSS_DELAY:
                self.agendar(
                    posicao_spawn(1, dist_min_tiles=8),
                    lambda p: Boss(p, mapa=1),
                    70)
                self.boss_criado = True

    def desenhar_avisos(self, surface, offset):
        """Desenha o circulo de aviso no chao. Quanto mais perto de nascer,
        mais cheio (vermelho) ele fica."""
        agora = pygame.time.get_ticks()
        for aviso in self.avisos:
            raio = aviso['raio']
            falta = max(0, aviso['quando'] - agora)
            progresso = 1 - falta / AVISO_DURACAO      # 0 -> 1 conforme o tempo passa
            cx = int(aviso['pos'][0] - offset.x)
            cy = int(aviso['pos'][1] - offset.y)
            circ = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
            pygame.draw.circle(circ, (255, 40, 40, 110), (raio, raio), int(raio * progresso))
            pygame.draw.circle(circ, (255, 40, 40, 200), (raio, raio), raio, 3)
            surface.blit(circ, (cx - raio, cy - raio))


def desenhar_barra_vida(surface, x, y, largura, altura, vida, vida_max):
    """Desenha uma barra de vida: fundo vermelho + parte verde proporcional."""
    if vida < 0:
        vida = 0
    fracao = vida / vida_max
    # fundo (vida perdida) em vermelho escuro
    pygame.draw.rect(surface, (90, 20, 20), (x, y, largura, altura))
    # vida atual em verde
    pygame.draw.rect(surface, (40, 200, 60), (x, y, int(largura * fracao), altura))
    # contorno
    pygame.draw.rect(surface, (15, 15, 15), (x, y, largura, altura), 2)


player      = Player()
camera      = Camera()
all_sprites_group.add(player)

spawner = GerenciadorSpawn()   # cuida de criar os inimigos (com atraso) de cada mapa

ENEMY_DANO_COOLDOWN = 45

fonte_hud = pygame.font.SysFont("arial", 24, bold=True)   # texto do HUD (moedas / chave)


# ── TELA DE INICIO 
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
        # botao muda de cor ao passar o mouse por cima
        pygame.draw.rect(screen, (90, 60, 140) if hover else (55, 40, 90), fundo_botao, border_radius=10)
        pygame.draw.rect(screen, (200, 180, 240), fundo_botao, 3, border_radius=10)
        screen.blit(texto_botao, botao_rect)

        pygame.display.update()
        clock.tick(FPS)


tela_inicio()


# ── TELA DE GAME OVER ──────────────────────────────────────────────────────────
def reiniciar_jogo():
    for b in bullet_group:
        b.kill()
    mundo.ir_para(0)

    # reseta o player
    player.health = player.max_health
    player.dano_cooldown = 0
    player.shot_cooldown = 0
    player.acabou_de_teleportar = False
    player.moedas = 0                    # zera as moedas ao reiniciar (a chave o spawner.iniciar zera)
    player.pos = pygame.math.Vector2(PLAYER_START_X, PLAYER_START_Y)
    player.hitbox_rect.center = (int(player.pos.x), int(player.pos.y))
    player.rect.center = player.hitbox_rect.center

    spawner.iniciar(0)   # limpa os inimigos e recomeca o spawn do mapa 1


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
        # botao "Jogar de Novo"
        pygame.draw.rect(screen, (120, 60, 60) if hover_jogar else (80, 40, 40), fundo_jogar, border_radius=10)
        pygame.draw.rect(screen, (240, 180, 180), fundo_jogar, 3, border_radius=10)
        screen.blit(texto_jogar, jogar_rect)
        # botao "Sair"
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
    spawner.update()   # cria os inimigos do mapa atual aos poucos (com atraso)

    # bala acerta um inimigo -> tira vida dele e a bala some.
    # se o inimigo morrer, o player ganha moedas e o spawner conta o kill
    # (o 5o kill dropa a chave).
    for bullet in bullet_group:
        for inimigo in pygame.sprite.spritecollide(bullet, enemy_group, False):
            morreu = inimigo.levar_dano(bullet.damage)
            bullet.kill()
            if morreu:
                player.moedas += inimigo.moedas
                spawner.registrar_kill(inimigo)

    # player encosta na chave -> pega a chave e libera o portal
    for item in item_group:
        if player.hitbox_rect.colliderect(item.rect):
            player.tem_chave = True
            item.kill()

    # inimigo encosta no player -> tira a vida do dano dele.
    # player.dano_cooldown = invencibilidade curta apos QUALQUER hit;
    # ataque_cooldown = cada inimigo espera antes de bater de novo.
    if player.dano_cooldown == 0:
        for inimigo in enemy_group:
            if inimigo.ataque_cooldown == 0 and player.hitbox_rect.colliderect(inimigo.rect):
                player.health -= inimigo.dano
                player.dano_cooldown = ENEMY_DANO_COOLDOWN
                inimigo.ataque_cooldown = inimigo.ataque_delay
                break

    # tiro do boss acerta o player -> tira o dano do tiro e o tiro some
    for tiro in enemy_bullet_group:
        if player.hitbox_rect.colliderect(tiro.rect):
            if player.dano_cooldown == 0:
                player.health -= tiro.dano
                player.dano_cooldown = ENEMY_DANO_COOLDOWN
            tiro.kill()

    # fim de jogo quando a vida do player zera: mostra o game over.
    # se o jogador escolher jogar de novo, reinicia e pula o resto do frame.
    if player.health <= 0:
        tela_game_over()
        reiniciar_jogo()
        continue

    camera.custom_draw()

    # barra de vida do PLAYER: fixa no canto superior esquerdo da tela (HUD)
    desenhar_barra_vida(screen, 20, 20, 200, 22, player.health, player.max_health)

    # HUD: moedas e status da chave
    screen.blit(fonte_hud.render(f"Moedas: {player.moedas}", True, (255, 220, 80)), (20, 52))
    falta = max(0, KILLS_PARA_CHAVE - spawner.kills)
    if player.tem_chave:
        texto_chave = fonte_hud.render("Chave: OK (portal liberado)", True, (120, 230, 120))
    elif spawner.chave_dropada:
        texto_chave = fonte_hud.render("Chave dropada! Pegue-a", True, (245, 215, 60))
    else:
        texto_chave = fonte_hud.render(f"Chave: faltam {falta} inimigos", True, (220, 220, 220))
    screen.blit(texto_chave, (20, 82))

    # aviso quando o player esta no portal sem a chave
    if player.no_portal and not player.tem_chave:
        aviso = fonte_hud.render("Voce precisa da chave pra usar o portal!", True, (255, 120, 120))
        screen.blit(aviso, aviso.get_rect(center=(LARGURA // 2, ALTURA - 60)))

    # barra de vida de cada INIMIGO: flutua logo acima do sprite, acompanhando o mapa
    for inimigo in enemy_group:
        bx = inimigo.rect.centerx - camera.offset.x - 25
        by = inimigo.rect.top     - camera.offset.y - 12
        desenhar_barra_vida(screen, bx, by, 50, 7, inimigo.health, inimigo.max_health)

    # DEBUG — descomenta pra ver as hitboxes
    # for box in mundo.hitboxes:
    #     pos = (box.x - camera.offset.x, box.y - camera.offset.y, box.width, box.height)
    #     pygame.draw.rect(screen, (255, 0, 0), pos, 1)

    pygame.display.update()
    clock.tick(FPS)