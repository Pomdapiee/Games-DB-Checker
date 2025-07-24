import discord
from discord.ext import commands, tasks
import requests
import json
import asyncio
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv
from discord import TextChannel

# Chargement des variables d'environnement
# load_dotenv() # Supprimé car Railway gère les variables d'environnement

# Configuration sécurisée
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DJANGO_API_URL = os.getenv("DJANGO_API_URL", "https://Pomdapie.pythonanywhere.com/api/games/")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# Vérification explicite
if not DISCORD_TOKEN:
    print("ERREUR: DISCORD_TOKEN manquant dans les variables Railway !")
if not DJANGO_API_URL:
    print("ERREUR: DJANGO_API_URL manquant dans les variables Railway !")
if not CHANNEL_ID:
    print("ERREUR: CHANNEL_ID manquant ou incorrect dans les variables Railway !")

print("[DEBUG] Début de l'initialisation du script")

print(f"[DEBUG] DISCORD_TOKEN: {'OK' if DISCORD_TOKEN else 'NON'}")
print(f"[DEBUG] DJANGO_API_URL: {DJANGO_API_URL}")
print(f"[DEBUG] CHANNEL_ID: {CHANNEL_ID}")

intents = discord.Intents.default()
intents.message_content = True

print("[DEBUG] Création du bot Discord...")
bot = commands.Bot(command_prefix='!', intents=intents)

# Fichier pour persister la base locale
KNOWN_GAMES_FILE = "known_games.json"

def load_known_games():
    """Charge la liste des jeux connus depuis le fichier"""
    try:
        if os.path.exists(KNOWN_GAMES_FILE):
            with open(KNOWN_GAMES_FILE, 'r', encoding='utf-8') as f:
                games_list = json.load(f)
                print(f"[DEBUG] {len(games_list)} jeux chargés depuis {KNOWN_GAMES_FILE}")
                return set(games_list)
        else:
            print(f"[DEBUG] Fichier {KNOWN_GAMES_FILE} non trouvé, démarrage avec base vide")
            return set()
    except Exception as e:
        print(f"[ERREUR] Impossible de charger {KNOWN_GAMES_FILE}: {e}")
        return set()

def save_known_games(games_set):
    """Sauvegarde la liste des jeux connus dans le fichier"""
    try:
        games_list = list(games_set)
        with open(KNOWN_GAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(games_list, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] {len(games_list)} jeux sauvegardés dans {KNOWN_GAMES_FILE}")
    except Exception as e:
        print(f"[ERREUR] Impossible de sauvegarder {KNOWN_GAMES_FILE}: {e}")

# Charger les jeux connus au démarrage
known_games = load_known_games()

class GameNotifier:
    def __init__(self):
        print("[DEBUG] Initialisation de GameNotifier...")
        self.session = requests.Session()
        # Plus besoin de headers pour l'API Django (pas d'authentification)
        print("[DEBUG] Session requests initialisée pour l'API Django")
    
    async def fetch_database(self):
        print("[DEBUG] fetch_database appelé...")
        try:
            print(f"[DEBUG] Requête GET vers {DJANGO_API_URL}")
            response = self.session.get(DJANGO_API_URL)
            print(f"[DEBUG] Statut de la réponse : {response.status_code}")
            response.raise_for_status()
            data = response.json()  # L'API Django retourne directement le dictionnaire des jeux
            print(f"[DEBUG] Données reçues : {list(data.keys())}")
            return data
        except requests.RequestException as e:
            print(f"[ERREUR] lors de la récupération de la DB: {e}")
            return {}
    
    async def create_game_embed(self, game_key, game_data):
        print(f"[DEBUG] Création de l'embed pour le jeu : {game_key}")
        embed = discord.Embed(
            title="🎮 Nouveau jeu ajouté !",
            color=0x00ff00,
            timestamp=datetime.now(FRENCH_TZ)
        )
        if 'description' in game_data and game_data['description']:
            description = game_data['description'][:1000]
            if len(game_data['description']) > 1000:
                description += "..."
            embed.description = f"**{game_data['official_name']}**\n{description}"
        else:
            embed.description = f"**{game_data['official_name']}**"
        if 'image_url' in game_data and game_data['image_url']:
            embed.set_image(url=game_data['image_url'])
        embed.set_footer(text=f"id: {game_key}")
        return embed
    
    async def check_for_new_games(self):
        print("[DEBUG] check_for_new_games appelé...")
        global known_games
        database = await self.fetch_database()
        print(f"[DEBUG] Contenu de la base récupérée : {list(database.keys())}")
        print(f"[DEBUG] known_games AVANT comparaison : {list(known_games)}")
        if not database:
            print("[DEBUG] Base vide ou inaccessible !")
            return []
        current_games = set(database.keys())
        new_game_keys = current_games - known_games
        print(f"[DEBUG] Nouveaux jeux détectés : {list(new_game_keys)}")
        new_games = [(game_key, database[game_key]) for game_key in new_game_keys]
        known_games = current_games

        # Sauvegarder la base locale mise à jour
        save_known_games(known_games)

        print(f"[DEBUG] known_games APRÈS mise à jour : {list(known_games)}")
        return new_games

notifier = GameNotifier()

FRENCH_TZ = pytz.timezone('Europe/Paris')
print(f"[DEBUG] FRENCH_TZ initialisé : {FRENCH_TZ}")

@bot.event
async def on_ready():
    print(f"[DEBUG] on_ready appelé à {datetime.now(FRENCH_TZ)}")
    print(f'Surveillance de la base de données activée')
    if not check_database.is_running():
        print("[DEBUG] Démarrage de la tâche planifiée check_database")
        check_database.start()
    else:
        print("[DEBUG] La tâche check_database est déjà en cours")

@tasks.loop(minutes=10)  # Vérification toutes les 10 minutes
async def check_database():
    print(f"[{datetime.now(pytz.utc)}] [DEBUG] check_database exécuté (heure UTC)")
    print(f"[{datetime.now(FRENCH_TZ)}] [DEBUG] check_database exécuté (heure Paris)")
    try:
        print("[DEBUG] Appel de notifier.check_for_new_games() (tâche planifiée)")
        new_games = await notifier.check_for_new_games()
        print(f"[DEBUG] Résultat de check_for_new_games (tâche planifiée) : {new_games}")
        if new_games:
            print("[DEBUG] De nouveaux jeux ont été détectés (tâche planifiée)")
            channel = bot.get_channel(CHANNEL_ID)
            print(f"[DEBUG] bot.get_channel({CHANNEL_ID}) => {channel}")
            if not isinstance(channel, TextChannel):
                print(f"[ERREUR] Canal {CHANNEL_ID} n'est pas un TextChannel !")
                return
            print(f"[DEBUG] Récupération du channel avec ID {CHANNEL_ID} : {channel}")
            if not channel or not hasattr(channel, "send"):
                print(f"[ERREUR] Canal {CHANNEL_ID} introuvable ou de type incorrect !")
                return
            for game_key, game_data in new_games:
                print(f"[DEBUG] Envoi de la notification pour le jeu : {game_key}")
                embed = await notifier.create_game_embed(game_key, game_data)
                await channel.send(embed=embed)
                print(f"[INFO] Nouveau jeu notifié: {game_data.get('official_name', game_key)}")
                await asyncio.sleep(1)
            print("[DEBUG] Tous les nouveaux jeux ont été notifiés (tâche planifiée).")
        else:
            print("[DEBUG] Aucun nouveau jeu détecté lors de la vérification automatique (tâche planifiée).")
    except Exception as e:
        print(f"[ERREUR] Exception dans check_database (tâche planifiée): {e}")

@check_database.before_loop
async def before_check_database():
    await bot.wait_until_ready()

@bot.command(name='status')
async def status(ctx):
    embed = discord.Embed(
        title="📊 Statut du Bot",
        color=0x0099ff,
        timestamp=datetime.now()
    )
    embed.add_field(
        name="Jeux surveillés | Statut surveillance",
        value=f"{len(known_games)} | {'🟢 Actif' if check_database.is_running() else '🔴 Inactif'}",
        inline=False
    )
    embed.add_field(name="Fréquence de vérification", value="Toutes les 10 minutes", inline=False)

    # Ajouter info sur la persistance
    persistence_status = "🟢 Actif" if os.path.exists(KNOWN_GAMES_FILE) else "🟡 Pas de fichier"
    embed.add_field(name="Persistance locale", value=persistence_status, inline=False)

    await ctx.send(embed=embed)

@bot.command(name='check_now')
@commands.has_permissions(administrator=True)
async def manual_check(ctx):
    await ctx.send("🔍 Vérification manuelle en cours...")
    try:
        new_games = await notifier.check_for_new_games()
        if new_games:
            for game_key, game_data in new_games:
                embed = await notifier.create_game_embed(game_key, game_data)
                await ctx.send(embed=embed)
        else:
            await ctx.send("ℹ️ Aucun nouveau jeu détecté.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de la vérification: {str(e)}")

@bot.command(name='reset_db')
@commands.has_permissions(administrator=True)
async def reset_database(ctx):
    global known_games
    known_games.clear()

    # Supprimer le fichier de persistance
    try:
        if os.path.exists(KNOWN_GAMES_FILE):
            os.remove(KNOWN_GAMES_FILE)
            print(f"[DEBUG] Fichier {KNOWN_GAMES_FILE} supprimé")
    except Exception as e:
        print(f"[ERREUR] Impossible de supprimer {KNOWN_GAMES_FILE}: {e}")

    await ctx.send("🔄 Base de données locale réinitialisée. La prochaine vérification va re-scanner tous les jeux.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous n'avez pas les permissions nécessaires pour cette commande.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Erreur de commande: {error}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
