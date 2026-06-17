import pygame
from sys import exit
import math
import os
from settings import *

pygame.init()

screen = pygame.display.set_mode((LARGURA, ALTURA))
pygame.display.set_caption('Jogo Bicalho')
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── MAPA ──────────────────────────────────────────────────────────────────────

TILE_SIZE = 16                   # tamanho do tile DENTRO da imagem tileset.png
TILE = TILE_SIZE * TILE_SCALE    # tamanho do tile NA TELA (ex: 16*3 = 48px)

# Tiles em que o jogador pode pisar. Qualquer outro número vira parede (colisão).
WALKABLE = {18, 27}

# Abre a imagem que tem todos os tiles e vê quantas colunas ela tem.
tileset_img = pygame.image.load(os.path.join(BASE_DIR, "tileset.png")).convert_alpha()
TILESET_COLUNAS = tileset_img.get_width() // TILE_SIZE


def carregar_csv(caminho):
    # Lê o arquivo do mapa e devolve uma lista de listas de números.
    mapa = []
    arquivo = open(caminho)
    for linha in arquivo:
        linha = linha.strip().rstrip(",")        # tira espaços e a vírgula do fim
        if linha != "":
            numeros = []
            for pedaco in linha.split(","):      # separa a linha pelas vírgulas
                numeros.append(int(pedaco))      # transforma cada texto em número
            mapa.append(numeros)
    arquivo.close()
    return mapa


def pegar_tile(tile_id):
    # Recorta da imagem o tile com esse número, já no tamanho da tela.
    indice = tile_id - 1                 # o tile 1 é o primeiro (índice 0)
    coluna = indice % TILESET_COLUNAS    # em que coluna ele está na imagem
    linha  = indice // TILESET_COLUNAS   # em que linha ele está na imagem
    area = pygame.Rect(coluna * TILE_SIZE, linha * TILE_SIZE, TILE_SIZE, TILE_SIZE)
    tile = tileset_img.subsurface(area)  # pega só aquele pedacinho da imagem
    return pygame.transform.scale(tile, (TILE, TILE))   # aumenta pro tamanho da tela


# Carrega o mapa do arquivo CSV.
mapa_csv = carregar_csv(os.path.join(BASE_DIR, "mapa 1.csv"))

# Tamanho total do mapa em pixels (a câmera usa isso pra não sair do mapa).
MAP_W = len(mapa_csv[0]) * TILE
MAP_H = len(mapa_csv) * TILE


def gerar_hitboxes(mapa):
    # Cria um retângulo de colisão (parede) pra cada tile que não é chão.
    hitboxes = []
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            tile_id = mapa[y][x]
            if tile_id not in WALKABLE:
                parede = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                hitboxes.append(parede)
    return hitboxes

hitboxes = gerar_hitboxes(mapa_csv)


def desenhar_mapa(surface, mapa, offset):
    # Desenha cada tile do mapa na tela, descontando a posição da câmera (offset).
    for y in range(len(mapa)):
        for x in range(len(mapa[y])):
            tile_id = mapa[y][x]
            if tile_id > 0:                       # 0 = vazio, não desenha
                tile = pegar_tile(tile_id)
                surface.blit(tile, (x * TILE - offset.x, y * TILE - offset.y))

# ── ANIMAÇÃO ──────────────────────────────────────────────────────────────────


IDLE_FRAMES   = 6    # Idle.png → 1386px ÷ 231 = 6 frames
WALK_FRAMES   = 8    # Run.png  → 1848px ÷ 231 = 8 frames
ATTACK_FRAMES = 4    # Hit.png  →  924px ÷ 231 = 4 frames
ANIM_SPEED    = 0.15 # velocidade da animação (frames por tick; maior = mais rápido)

def carregar_animacao(nome_arquivo, num_frames, escala, fallback="hero.png"):
    """Fatia uma sprite sheet horizontal em uma lista de frames já escalados.
    Se o arquivo não existir, usa o fallback como animação de 1 frame."""
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

    # fallback: ainda não há sprite sheet, usa a imagem única antiga
    img = pygame.image.load(os.path.join(BASE_DIR, fallback)).convert_alpha()
    return [pygame.transform.rotozoom(img, 0, escala)]

def normalizar_frames(animations):
    """Coloca TODOS os frames no mesmo tamanho de canvas, centralizados.
    Isso impede o personagem de 'pular' de lugar (teletransporte visual)
    quando os frames têm tamanhos diferentes entre si."""
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

# ── SPRITES ───────────────────────────────────────────────────────────────────

all_sprites_group = pygame.sprite.Group()
bullet_group       = pygame.sprite.Group()
enemy_group        = pygame.sprite.Group()

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()

        # Dicionário com todas as animações já carregadas e escaladas
        self.animations = {
            'idle':   carregar_animacao('Idle.png', IDLE_FRAMES,   PLAYER_SIZE),
            'walk':   carregar_animacao('Run.png',  WALK_FRAMES,   PLAYER_SIZE),
            'attack': carregar_animacao('Hit.png',  ATTACK_FRAMES, PLAYER_SIZE),
        }
        # Deixa todos os frames do mesmo tamanho (evita o teletransporte visual)
        self.animations = normalizar_frames(self.animations)

        self.state        = 'idle'   # estado atual da animação
        self.frame_index  = 0.0      # frame atual (float, pra controlar a velocidade)
        self.attacking    = False    # True enquanto a animação de ataque toca
        self.angle        = 0        # ângulo em direção ao mouse (usado pelos tiros)
        self.facing_left  = False    # pra qual lado o boneco está virado

        # A imagem base é o frame atual; player_aim() decide o flip
        self.base_player_image = self.animations['idle'][0]
        self.image = self.base_player_image

        self.pos = pygame.math.Vector2(PLAYER_START_X, PLAYER_START_Y)
        # Hitbox pequena (só o corpo do mago), não o sprite inteiro. O sprite
        # continua grande; só a COLISÃO é menor, pra passar por portas/corredores.
        self.hitbox_rect = pygame.Rect(0, 0, 40, 52)
        self.hitbox_rect.center = self.pos
        self.rect = self.hitbox_rect.copy()

        self.shoot = False
        self.speed = PLAYER_SPEED
        self.shot_cooldown = 0
        self.gun_barrel_offset = pygame.math.Vector2(GUN_OFFSET_X, GUNOFFSET_Y)

    def player_aim(self):
        # Calcula o ângulo até o mouse — usado SÓ pelos tiros, não pra girar o boneco
        self.mouse_coords = pygame.mouse.get_pos()
        self.x_change_mouse_player = self.mouse_coords[0] - LARGURA // 2
        self.y_change_mouse_player = self.mouse_coords[1] - ALTURA  // 2
        self.angle = math.degrees(
            math.atan2(self.y_change_mouse_player, self.x_change_mouse_player))

        # Vira o boneco pro lado do mouse SEM deitar ele (espelha na horizontal).
        # Mantém o último lado quando o mouse está bem no centro, pra não tremer.
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
            # Dispara o tiro
            spawn_pos = self.pos + self.gun_barrel_offset.rotate(self.angle)
            bullet = Bullet(spawn_pos.x, spawn_pos.y, self.angle)
            bullet_group.add(bullet)
            all_sprites_group.add(bullet)
            # Dispara a animação de ataque (reinicia do começo a cada tiro)
            self.attacking   = True
            self.frame_index = 0.0

    def set_state(self):
        """Decide qual animação tocar. Ataque tem prioridade e trava até terminar."""
        if self.attacking:
            novo = 'attack'
        elif self.velocity_x != 0 or self.velocity_y != 0:
            novo = 'walk'
        else:
            novo = 'idle'

        # Ao trocar de estado, reinicia o índice (evita estourar o tamanho da lista)
        if novo != self.state:
            self.state = novo
            self.frame_index = 0.0

    def animate(self):
        animation = self.animations[self.state]

        self.frame_index += ANIM_SPEED
        if self.frame_index >= len(animation):
            self.frame_index = 0.0
            if self.state == 'attack':
                self.attacking = False   # terminou o golpe, volta pro idle/walk

        self.base_player_image = animation[int(self.frame_index)]

    def move(self):
        # X
        self.pos.x += self.velocity_x
        self.hitbox_rect.centerx = int(self.pos.x)
        for box in hitboxes:
            if self.hitbox_rect.colliderect(box):
                if self.velocity_x > 0:
                    self.hitbox_rect.right = box.left
                else:
                    self.hitbox_rect.left  = box.right
                self.pos.x = self.hitbox_rect.centerx

        # Y
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

    def update(self):
        self.user_input()       # movimento + dispara ataque
        self.move()
        self.set_state()        # escolhe idle / walk / attack
        self.animate()          # avança o frame da animação
        self.player_aim()       # mira no mouse + espelha o boneco pro lado certo
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

        # Trava a câmera nas bordas do mapa (impede mostrar o "preto" fora do mapa)
        self.offset.x = max(0, min(self.offset.x, MAP_W - LARGURA))
        self.offset.y = max(0, min(self.offset.y, MAP_H - ALTURA))

        desenhar_mapa(screen, mapa_csv, self.offset)

        for sprite in all_sprites_group:
            screen.blit(sprite.image, sprite.rect.topleft - self.offset)

# ── INSTÂNCIAS ────────────────────────────────────────────────────────────────

player      = Player()
camera      = Camera()
necromancer = Enemy((400, 400))

all_sprites_group.add(player)

# ── GAME LOOP ─────────────────────────────────────────────────────────────────

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    screen.fill((0, 0, 0))          # limpa a tela (evita rastro dos sprites)
    all_sprites_group.update()      # atualiza primeiro...
    camera.custom_draw()            # ...depois desenha

    # DEBUG — remova quando as hitboxes estiverem certas
    # for box in hitboxes:
    #     pos = (box.x - camera.offset.x, box.y - camera.offset.y, box.width, box.height)
    #     pygame.draw.rect(screen, (255, 0, 0), pos, 1)

    pygame.display.update()
    clock.tick(FPS)