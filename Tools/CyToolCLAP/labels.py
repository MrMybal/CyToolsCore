"""English prompts for CLAP, French display labels. Candidate sets are explicit."""
SOUNDS = [
    ('Chien qui aboie','The sound of a dog barking.'),
    ('Chat qui miaule','The sound of a cat meowing.'),
    ('Chant d’oiseaux','The sound of birds chirping and singing.'),
    ('Pluie','The sound of rain falling.'),
    ('Vagues','The sound of ocean waves crashing on a beach.'),
    ('Vent','The sound of strong wind blowing.'),
    ('Tonnerre','The sound of thunder during a storm.'),
    ('Moteur','The sound of a motor vehicle engine running.'),
    ('Sirène','The sound of an emergency siren.'),
    ('Aspirateur','The sound of a vacuum cleaner running.'),
    ('Applaudissements','The sound of a crowd clapping and applauding.'),
    ('Rires','The sound of people laughing.'),
    ('Parole','The sound of a person speaking.'),
    ('Pas','The sound of footsteps walking.'),
    ('Clavier','The sound of typing on a computer keyboard.'),
    ('Sonnette','The sound of a doorbell ringing.'),
]
MUSIC = [
    ('Piano','The sound of solo piano music.'),
    ('Guitare acoustique','The sound of acoustic guitar music.'),
    ('Guitare électrique rock','The sound of rock music with electric guitar and drums.'),
    ('Trompette','The sound of a trumpet playing a melody.'),
    ('Saxophone','The sound of a saxophone playing music.'),
    ('Violon','The sound of solo violin music.'),
    ('Orchestre classique','The sound of classical orchestral music with strings.'),
    ('Batterie','The sound of a drum kit playing a rhythm.'),
    ('Musique électronique','The sound of electronic dance music with synthesizers.'),
    ('Jazz','The sound of jazz music with piano, bass and drums.'),
    ('Chant','The sound of a person singing a song.'),
    ('Chœur','The sound of a choir singing.'),
]

def candidates(preset, custom=None):
    if custom is not None:
        return [(text,text) for text in custom]
    if preset=='sounds': return SOUNDS
    if preset=='music': return MUSIC
    return SOUNDS+MUSIC
