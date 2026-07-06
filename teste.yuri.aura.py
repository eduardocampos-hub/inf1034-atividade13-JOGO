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

tileset_img = pygame.image.load(os.path.join(BASE_DIR, "tileset.png")).convert_alpha()
TILESET_COLUNAS = tileset_img.get_width() // TILE_SIZE


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


def pegar_tile(tile_id):
    indice = tile_id - 1
    coluna = indice % TILESET_COLUNAS
    linha  = indice // TILESET_COLUNAS
    area = pygame.Rect(coluna * TILE_SIZE, linha * TILE_SIZE, TILE_SIZE, TILE_SIZE)
    tile = tileset_img.subsurface(area)
    return pygame.transform.scale(tile, (TILE, TILE))


def gerar_mapa_plano(colunas, linhas, piso=MAPA2_PISO):
    """Cria um mapa todo de chao (completamente plano)."""
    return [[piso for _ in range(colunas)] for _ in range(linhas)]


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

# Segundo mapa: completamente plano, com 1 portal no meio.
mapa2 = gerar_mapa_plano(MAPA2_COLUNAS, MAPA2_LINHAS, MAPA2_PISO)
mapa2[MAPA2_LINHAS // 2][MAPA2_COLUNAS // 2] = TELEPORTE_ID

PORTAL_SURF = surface_teleporte()   # usado pelo desenhar_mapa

# Tudo que muda quando troca de mapa fica em listas (indice = qual mapa).
mapas            = [mapa_csv, mapa2]
mapw_mapas       = [len(mapa_csv[0]) * TILE, len(mapa2[0]) * TILE]
maph_mapas       = [len(mapa_csv) * TILE,    len(mapa2) * TILE]
teleportes_mapas = [achar_tile(mapa_csv, TELEPORTE_ID), achar_tile(mapa2, TELEPORTE_ID)]
mapa_atual = 0

MAP_W = mapw_mapas[mapa_atual]
MAP_H = maph_mapas[mapa_atual]


def gerar_hitboxes(mapa):
    hitboxes = []
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            tile_id = mapa[y][x]
            if tile_id not in WALKABLE:
                parede = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                hitboxes.append(parede)
    return hitboxes

hitboxes_mapas = [gerar_hitboxes(mapa_csv), gerar_hitboxes(mapa2)]
hitboxes = hitboxes_mapas[mapa_atual]


def trocar_mapa():
    """Troca o mapa ATIVO e poe o jogador em cima do portal do outro mapa.
    So reaponta as globais que o resto do jogo ja usa: mapa_csv, hitboxes,
    MAP_W e MAP_H (este ultimo a camera usa pra travar nas bordas)."""
    global mapa_atual, mapa_csv, hitboxes, MAP_W, MAP_H
    mapa_atual = 1 - mapa_atual            # alterna entre 0 e 1
    mapa_csv = mapas[mapa_atual]
    hitboxes = hitboxes_mapas[mapa_atual]
    MAP_W = mapw_mapas[mapa_atual]
    MAP_H = maph_mapas[mapa_atual]
    col, row = teleportes_mapas[mapa_atual]
    player.pos.x = col * TILE + TILE // 2
    player.pos.y = row * TILE + TILE // 2
    player.hitbox_rect.center = (int(player.pos.x), int(player.pos.y))
    player.rect.center = player.hitbox_rect.center
    player.desencostar_paredes()   # nao deixa o player nascer preso numa parede


def desenhar_mapa(surface, mapa, offset):
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            tile_id = mapa[y][x]
            if tile_id <= 0:
                continue
            if tile_id == TELEPORTE_ID:
                tile = PORTAL_SURF          # o portal tem desenho proprio
            else:
                tile = pegar_tile(tile_id)
            surface.blit(tile, (x * TILE - offset.x, y * TILE - offset.y))

# Animação

IDLE_FRAMES   = 6    # Idle.png → 6 frames
WALK_FRAMES   = 8    # Run.png  → 8 frames
ATTACK_FRAMES = 4    # Hit.png  → 4 frames
ANIM_SPEED    = 0.15

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

        self.max_health = 3        # vida maxima do personagem principal
        self.health = self.max_health
        self.dano_cooldown = 0     # tempo de invencibilidade apos tomar dano

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
        for box in hitboxes:
            if self.hitbox_rect.colliderect(box):
                if self.velocity_x > 0:
                    self.hitbox_rect.right = box.left
                else:
                    self.hitbox_rect.left  = box.right
                self.pos.x = self.hitbox_rect.centerx

        self.pos.y += self.velocity_y
        self.hitbox_rect.centery = int(self.pos.y)
        for box in hitboxes:
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
        for box in hitboxes:
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
        em_cima = (0 <= row < len(mapa_csv) and 0 <= col < len(mapa_csv[row])
                   and mapa_csv[row][col] == TELEPORTE_ID)

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


class Enemy(pygame.sprite.Sprite):
    def __init__(self, position):
        super().__init__(enemy_group, all_sprites_group)
        self.image = pygame.transform.rotozoom(
            pygame.image.load('0.png').convert_alpha(), 0, 2)
        self.rect  = self.image.get_rect(center=position)
        self.position  = pygame.math.Vector2(position)
        self.direction = pygame.math.Vector2()
        self.speed = ENEMY_SPEED
        self.max_health = 5             # vida maxima do necromante
        self.health = self.max_health

    def hunt_player(self):
        pv = pygame.math.Vector2(player.hitbox_rect.center)
        ev = pygame.math.Vector2(self.rect.center)
        dist = (pv - ev).magnitude()
        self.direction = (pv - ev).normalize() if dist > 0 else pygame.math.Vector2()
        self.position += self.direction * self.speed
        self.rect.center = (int(self.position.x), int(self.position.y))

    def levar_dano(self, dano):         # tira vida e morre quando chega a 0
        self.health -= dano
        if self.health <= 0:
            self.kill()

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
        self.offset.x = max(0, min(self.offset.x, MAP_W - LARGURA))
        self.offset.y = max(0, min(self.offset.y, MAP_H - ALTURA))

        desenhar_mapa(screen, mapa_csv, self.offset)

        for sprite in all_sprites_group:
            screen.blit(sprite.image, sprite.rect.topleft - self.offset)


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
necromancer = Enemy((400, 400))

all_sprites_group.add(player)

ENEMY_DANO_COOLDOWN = 45   # ~0.75s a 60fps de invencibilidade do player ao tomar dano


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    screen.fill((0, 0, 0))
    all_sprites_group.update()

    # bala acerta o necromante -> tira vida dele e a bala some
    for bullet in bullet_group:
        for inimigo in pygame.sprite.spritecollide(bullet, enemy_group, False):
            inimigo.levar_dano(bullet.damage)
            bullet.kill()

    # necromante encosta no player -> tira 1 de vida (respeitando a invencibilidade)
    if player.dano_cooldown == 0:
        for inimigo in enemy_group:
            if player.hitbox_rect.colliderect(inimigo.rect):
                player.health -= 1
                player.dano_cooldown = ENEMY_DANO_COOLDOWN
                break

    # fim de jogo quando a vida do player zera
    if player.health <= 0:
        pygame.quit()
        exit()

    camera.custom_draw()

    # barra de vida do PLAYER: fixa no canto superior esquerdo da tela (HUD)
    desenhar_barra_vida(screen, 20, 20, 200, 22, player.health, player.max_health)

    # barra de vida de cada INIMIGO: flutua logo acima do sprite, acompanhando o mapa
    for inimigo in enemy_group:
        bx = inimigo.rect.centerx - camera.offset.x - 25
        by = inimigo.rect.top     - camera.offset.y - 12
        desenhar_barra_vida(screen, bx, by, 50, 7, inimigo.health, inimigo.max_health)

    # DEBUG — descomenta pra ver as hitboxes
    # for box in hitboxes:
    #     pos = (box.x - camera.offset.x, box.y - camera.offset.y, box.width, box.height)
    #     pygame.draw.rect(screen, (255, 0, 0), pos, 1)

    pygame.display.update()
    clock.tick(FPS) 