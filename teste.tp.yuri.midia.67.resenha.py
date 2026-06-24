import pygame
from sys import exit
import math
import os
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


def gerar_mapa_plano(colunas, linhas, piso=MAPA2_PISO):
    """Carrega o MAPA 3 (duas camadas: chao por baixo + parede por cima) e
    devolve (chao, parede). Se os arquivos do mapa 3 nao existirem, cai no
    mapa plano antigo (uma camada so de chao), devolvendo (None, plano)."""
    chao_path   = os.path.join(BASE_DIR, "mapa 3_chao.csv")
    parede_path = os.path.join(BASE_DIR, "mapa 3_parede.csv")
    if os.path.exists(chao_path) and os.path.exists(parede_path):
        return carregar_csv(chao_path), carregar_csv(parede_path)
    plano = [[piso for _ in range(colunas)] for _ in range(linhas)]
    return None, plano


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

# Segundo mapa: o MAPA 3 (chao + parede), com 1 portal no meio.
# 'mapa2' eh a camada de PAREDE (colisao + desenhada por cima); 'chao2' eh o
# piso desenhado por baixo. No mapa 3 o vazio andavel eh -1; no fallback plano
# o chao usa os tiles do conjunto WALKABLE.
chao2, mapa2 = gerar_mapa_plano(MAPA2_COLUNAS, MAPA2_LINHAS, MAPA2_PISO)
mapa2[len(mapa2) // 2][len(mapa2[0]) // 2] = TELEPORTE_ID
WALKABLE2 = {-1, TELEPORTE_ID} if chao2 is not None else WALKABLE

PORTAL_SURF = surface_teleporte()   # usado pelo desenhar_mapa

# Tudo que muda quando troca de mapa fica em listas (indice = qual mapa).
mapas            = [mapa_csv, mapa2]                 # camada de colisao/topo
chaos            = [None, chao2]                     # camada de piso (ou None)
walkables_mapas  = [WALKABLE, WALKABLE2]             # o que eh andavel em cada um
# tileset (imagem, colunas) de cada CAMADA. Mapa 1 so tem a camada principal.
ts_principal_mapas = [TS_MAPA1, TS_WALL]             # tileset da parede/topo
ts_chao_mapas      = [None,     TS_GRASS]            # tileset do piso (ou None)
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
    """Guarda o estado do mapa ATIVO (mapa, chao, hitboxes, tilesets, tamanho).
    Trocar de mapa = so mexer nos atributos deste objeto; por isso o resto do
    codigo nao precisa de 'global', ele le sempre 'mundo.algo'."""
    def __init__(self, indice=0):
        self.ir_para(indice)

    def ir_para(self, indice):
        self.indice  = indice
        self.mapa = mapas[indice]            # camada de colisao/topo
        self.chao = chaos[indice]            # camada de piso (ou None)
        self.hitboxes = hitboxes_mapas[indice]
        self.ts_principal = ts_principal_mapas[indice]
        self.ts_chao = ts_chao_mapas[indice]
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
    if chao is not None:                            # mapa 3: piso por baixo (Grass)
        desenhar_camada(surface, chao, offset, ts_chao)
    desenhar_camada(surface, mapa, offset, ts_principal)  # paredes/tiles por cima (Wall)

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

all_sprites_group = pygame.sprite.Group()
bullet_group       = pygame.sprite.Group()
enemy_group        = pygame.sprite.Group()

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

        if em_cima:
            if not self.acabou_de_teleportar:
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

    def update(self):
        self.x += self.x_vel
        self.y += self.y_vel
        self.rect.center = (int(self.x), int(self.y))
        if pygame.time.get_ticks() - self.spawn_time > BULLET_LIFETIME:
            self.kill()


class Enemy(pygame.sprite.Sprite):
    def __init__(self, position):
        super().__init__(enemy_group, all_sprites_group)
        self.image = pygame.transform.rotozoom(
            pygame.image.load('0.png').convert_alpha(), 0, 2)
        self.rect  = self.image.get_rect(center=position)
        self.position  = pygame.math.Vector2(position)
        self.direction = pygame.math.Vector2()
        self.speed = ENEMY_SPEED

    def hunt_player(self):
        pv = pygame.math.Vector2(player.hitbox_rect.center)
        ev = pygame.math.Vector2(self.rect.center)
        dist = (pv - ev).magnitude()
        self.direction = (pv - ev).normalize() if dist > 0 else pygame.math.Vector2()
        self.position += self.direction * self.speed
        self.rect.center = (int(self.position.x), int(self.position.y))

    def update(self):
        self.hunt_player()


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

        desenhar_mapa(screen, mundo.chao, mundo.mapa, self.offset, mundo.ts_chao, mundo.ts_principal)

        for sprite in all_sprites_group:
            screen.blit(sprite.image, sprite.rect.topleft - self.offset)


player      = Player()
camera      = Camera()
necromancer = Enemy((400, 400))

all_sprites_group.add(player)


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    screen.fill((0, 0, 0))
    all_sprites_group.update()
    camera.custom_draw()

    # DEBUG — descomenta pra ver as hitboxes
    # for box in mundo.hitboxes:
    #     pos = (box.x - camera.offset.x, box.y - camera.offset.y, box.width, box.height)
    #     pygame.draw.rect(screen, (255, 0, 0), pos, 1)

    pygame.display.update()
    clock.tick(FPS)