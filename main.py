import pygame
from sys import exit
import math
from settings import *

pygame.init()

# criando a janela
screen = pygame.display.set_mode((LARGURA, ALTURA))
pygame.display.set_caption('Jogo Bicalho')
clock = pygame.time.Clock()


# imagens
background = pygame.transform.scale(pygame.image.load("C:/Users/nuvem/Desktop/inf1034-atividade13-JOGO/background.png").convert(), (LARGURA, ALTURA))

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.transform.rotozoom(pygame.image.load('C:/Users/nuvem/Desktop/inf1034-atividade13-JOGO/Hero_Walk_01.png').convert_alpha(), 0, 0.62)
        self.pos = pygame.math.Vector2(PLAYER_START_X, PLAYER_START_Y)

player = Player()

while True:
    keys = pygame.key.get_pressed()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    screen.blit(background, (0,0))
    screen.blit(player.image, player.pos)
    pygame.display.update()
    clock.tick(FPS)