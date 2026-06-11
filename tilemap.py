import os
import pygame
import random
from settings import *

# pasta onde este arquivo esta (funciona mesmo se o terminal estiver em outra pasta)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TILE_SIZE = 16  # tamanho do tile no tile.png

# coordenadas (x, y) dos tiles dentro do tile.png
FLOOR_TILE = (80, 16)                                # chao vermelho liso
ROCK_TILES = [(128, 80), (144, 80), (160, 80)]       # variacoes com pedras
BRICK_TILE = (96, 32)                                # tijolo (parede)


def _get_tile(sheet, x, y, size):
    tile = sheet.subsurface(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
    return pygame.transform.scale(tile, (size, size))


def make_lava_tile():
    """Gera um tile de lava em pixel art (nao existe lava no tileset)."""
    rng = random.Random(7)
    mini = pygame.Surface((TILE_SIZE, TILE_SIZE))
    base = (207, 87, 27)        # laranja base
    escuro = (158, 40, 16)      # vermelho escuro
    claro = (252, 163, 38)      # laranja claro
    brilho = (255, 224, 112)    # amarelo brilhante
    for y in range(TILE_SIZE):
        for x in range(TILE_SIZE):
            r = rng.random()
            if r < 0.06:
                cor = brilho
            elif r < 0.22:
                cor = claro
            elif r < 0.45:
                cor = escuro
            else:
                cor = base
    # blobs escuros pra dar textura de crosta
            mini.set_at((x, y), cor)
    for _ in range(4):
        bx, by = rng.randint(1, 13), rng.randint(1, 13)
        for dx in range(3):
            for dy in range(2):
                mini.set_at((bx+dx, by+dy), escuro)
    size = int(TILE_SIZE * TILE_SCALE)
    return pygame.transform.scale(mini, (size, size))


def build_map():
    """Gera a superficie do mapa e a lista de retangulos de colisao das bordas.

    Retorna: (background_surface, wall_rects)
    """
    # procura o tileset por estes nomes, na ordem
    candidatos = ['tile.png', 'tileset.png', 'background.png']
    caminho = None
    for nome in candidatos:
        teste = os.path.join(BASE_DIR, nome)
        if os.path.exists(teste):
            caminho = teste
            break
    if caminho is None:
        raise FileNotFoundError(
            'Tileset nao encontrado. Salve a imagem do tileset como tile.png '
            'na pasta do jogo: ' + BASE_DIR)
    sheet = pygame.image.load(caminho).convert()

    # se a imagem foi salva ampliada/reduzida, ajusta de volta pro tamanho original
    if sheet.get_size() != (192, 128):
        sheet = pygame.transform.scale(sheet, (192, 128))
    size = int(TILE_SIZE * TILE_SCALE)

    floor = _get_tile(sheet, *FLOOR_TILE, size)
    rocks = [_get_tile(sheet, x, y, size) for (x, y) in ROCK_TILES]
    brick = _get_tile(sheet, *BRICK_TILE, size)

    map_w = MAP_WIDTH * size
    map_h = MAP_HEIGHT * size
    surface = pygame.Surface((map_w, map_h))

    rng = random.Random(42)  # seed fixa: o mapa fica igual toda vez

    for ty in range(MAP_HEIGHT):
        for tx in range(MAP_WIDTH):
            px, py = tx * size, ty * size
            is_border = (tx == 0 or ty == 0 or
                         tx == MAP_WIDTH - 1 or ty == MAP_HEIGHT - 1)
            if is_border:
                surface.blit(brick, (px, py))
            else:
                # ~12% de chance de usar um tile com pedras pra variar o chao
                if rng.random() < 0.12:
                    surface.blit(rng.choice(rocks), (px, py))
                else:
                    surface.blit(floor, (px, py))

    # 4 retangulos grandes cobrindo as bordas (mais rapido que 1 rect por tile)
    wall_rects = [
        pygame.Rect(0, 0, map_w, size),                # topo
        pygame.Rect(0, map_h - size, map_w, size),     # baixo
        pygame.Rect(0, 0, size, map_h),                # esquerda
        pygame.Rect(map_w - size, 0, size, map_h),     # direita
    ]

    return surface, wall_rects, make_lava_tile()
