# IMPORTS

# Working with files
from os import listdir, environ
from os.path import exists
from zipfile import ZipFile # .jar

# Working with json/toml formats
from toml import loads
from json import dumps, load

# Working with web stuff
from requests import get
from urllib.parse import quote

# CONSTS
HEADERS = {
    "Accept": "application/json",
    "x-api-key": environ.get("CFKEY")
} # Request headers
MODLOADERS = {
    "forge": 1,
    "fabric": 4,
    "quilt": 5
} # Modloader indexes

# FUNCTIONS

# Get curseforge info
def _get_curse_page(info:dict, version:str, modloader:str) -> dict:
    replacements = {
        " ": "-", # Replace spaces with dashes
        
        # Punctuation remover
        "'": "",
        "(": "",
        ")": "",
        ":": "",

        # Add - after some mod's name
        "integrated": "integrated-",
        "rftools": "rftools-",
        "rs": "rs-",

        # Shorten names
        "industrial-agriculture-plugin": "iap",

        "--": "-" # Replace accidental double dash
    } # Replacements for string formating
    slug = info["displayName"].lower() # Get the most likely slug
    for k, v in replacements.items(): slug = slug.replace(k, v) # Format

    # Possible slugs on curseforge (because curseforge ids/slugs are not related to modIds for some reason)
    possiblepages = [
        slug, # The most likely slug (displayName with formating)
        info["modId"], # The second most likely slug (basic modId)

        # Specialized slugs
        slug+"-"+modloader, # slug-forge/slug-fabric
        slug+"-1-8", # slug-1-8 (needed for mods ending in 1.8+)
        slug+"-api", # slug-api (I love architectury)
        slug+"_", # slug_ (slug. for example "Shrink.")
        slug+"-"+info["modId"], # slug-modid (yep, some mods do that)

        slug.replace("-", ""), # slugsecondword
        slug.replace("library", "lib"), # slug-lib (mostly needed for supermartijn642s-config-lib)

        slug[:-1] # I forgor why this is here
    ]

    # Names that just don't want to work so I added them as exceptions
    exceptions = {
        "mgui": "mutil",
        "kubejs-additons-forge": "kubejs-additions",
        "clickadv-mod": "clickable-advancements",
        "just-enough-resources": "just-enough-resources-jer",
        "space-bosstools": "beyond-earth",
        "thermal-series": "thermal-foundation",
        "elevator-mod": "openblocks-elevator",
        "fastleafdecay": "fast-leaf-decay",
        "hyper-lighting-core": "hyper-lighting-colored-light-core",
        "commoncapabilities": "common-capabilities",
        "enders-torage": "ender-storage-1-8",
        "simple-rpc": "simple-discord-rpc",

        "time-in-a-bottle": ("time-in-a-bottle-standalone" if modloader=="forge" else "time-in-a-bottle") # Fabric's mod's name is just time-in-a-bottle, why?
    }

    # For each possible slug
    for p in possiblepages:
        if slug in exceptions.keys(): p = exceptions[slug] # If in exceptions, just use the exception

        # Get the mod
        res = get("https://api.curseforge.com/v1/mods/search", params={
            "gameid": 432, # 432 is for minecraft
            "pageSize": 1, # Get only 1 mod
            "slug": p
        }, headers=HEADERS).json()

        if res["data"] != []: # If it finds a mod
            fileinfo = [i for i in res["data"][0]["latestFilesIndexes"] if i["gameVersion"]==version and i["modLoader"] in (MODLOADERS[modloader], None)] # Get a valid file
            if  len(fileinfo)>0: return res["data"][0], fileinfo[0] # If a valid file is available, returns info about mod and file

    _handle_exception(f"Couldn't find mod {info['displayName']} for modloader {modloader} and version {version}. If you believe this is an error, report this to our github: https://github.com/Modern-Modpacks/modern-manifest-generator/issues/new?title={quote(f'{slug} ({modloader})')}&labels=Unknown+mod&body={quote(str(possiblepages))}") # If it couldn't find the mod, throws an error with a specialized github link
# Get mod info
def _get_mod_info(file:str, ingoreerrs:bool, v:bool, version:str, modloader:str) -> dict:
    mod = ZipFile(file) # Open mod.jar
    try: modinfofile = mod.open("META-INF/mods.toml") # Find metadata toml
    except KeyError: _handle_exception(f"Bad file: {file}", ingoreerrs, v) # If it can't find the toml file, fail
    modinfostr = modinfofile.read().decode("utf-8") # Decode metadata
    modinfo = loads(modinfostr)["mods"][0] # Get needed info in a dict

    # Pass info to the previous function and get curse data
    curseinfo = _get_curse_page(modinfo, version, modloader)

    modinfofile.close() # Close file for security :)

    return curseinfo # Pass data to the next function
# Get modloader version
def _get_modloader_version(modloader:str, modloaderversion:str) -> str:
    if modloader not in MODLOADERS.keys(): _handle_exception("Invalid modloader") # Throw error if modloader is some random garbage
    if modloaderversion==None: # If modloader version not specified
        if modloader!="forge": _handle_exception("You must specify the modloader version since you are not using forge. Do that with the --modloaderversion argument.") # If not forge, err

        versions = get("https://api.curseforge.com/v1/minecraft/modloader", headers=HEADERS).json()["data"] # Get all versions of forge
        modloaderversion = [i for i in versions if i["gameVersion"]==version and i["latest"]][0]["name"] # Select the latest one for the minecraft version

        if verbose: print(f"\nModloader version not specified. Using {modloaderversion}.") # Inform
    else: modloaderversion = f"{modloader}-{modloaderversion}" # Else set modloaderversion to modloader name + specified version

    return modloaderversion # Return version formated

# Handle an error
def _handle_exception(err:str, ignore:bool=False, verbose:bool=True):
    if not ignore or verbose: print(err) # If error can be ignored and ingore mode is active and verbose mode is not, don't print the error
    if not ignore: exit(1) # If can be ignored and ignore mod on, skip error

# Construct a manifest (main function)
def _construct_manifest(path:str=None, *, name:str, version:str="1.16.5", author:str="Modern Modpacks", modpackversion:str="1.0", overrides:str="overrides", modloader:str="forge", modloaderversion:str=None, resetcache:bool=False, verbose:bool=True, debug:bool=False, skiperrs:bool=False) -> dict:
    if get("https://api.curseforge.com/v1/games", headers=HEADERS).status_code==403: _handle_exception("CFKEY not set or invalid. Read instructions on our github page again if you don't know what this means.") # Check if CFKEY is set

    # Modloader stuff
    modloader = modloader.lower() # Format
    modpackversion = _get_modloader_version(modloader, modloaderversion) # Format again

    # Manifest
    if exists("manifest.json"): manifest = load(open("manifest.json")) # If it already exists, open it.
    else: # If not, create template
        manifest = {
            # CF boilerplate
            "manifestType":  "minecraftModpack",
            "manifestVersion": 1,

            "files": [], # Actual mods

            # Modpack info
            "name": name, # Name
            "version": modpackversion, # Version
            "overrides": overrides, # Overrides folder
            "author": author, # Author
            "minecraft": { # Minecraft instance info
                "version": version, # Minecraft version
                "modLoaders":  [
                    {
                        "id": modloaderversion, # Modloader + it's version
                        "primary": True
                    }
                ]
            }
        }

    mods = sorted([f for f in listdir() if f.endswith(".jar")]) # Get mod files sorted

    # Cache
    if exists("manifest.cache.json") and exists("manifest.json") and not resetcache: # If cache and manifest already exist (+ no --resetcache option)
        cache = load(open("manifest.cache.json")) # Open cache
        for mod, modid in cache.items(): # For every cached mod
            if mod in mods: mods.remove(mod) # Remove in mod file list if in mods
            else: # If mod was deleted
                del cache[mod] # Remove in cache
                manifest["files"].remove([i for i in manifest["files"] if i["projectID"]==modid][0]) # Remove in manifest 
    else: cache = {} # If no cache found, set it to an empty dict

    # Verbose shit
    if verbose: print("\nStarting manifest generation... (It can take a lot of time depending on the amound of mods and your internet speed. So grab some tea while you're at it!)\n") # Starting gen
    if verbose and skiperrs: print("WARNING! The skip-errors mode is turned off. This may cause some issues in your final manifest.\n") # If skip-errors, inform
    if verbose and debug: print("Debug mode is enabled. Some additional information will be displayed.\n") # If debug, inform

    # Main modlist generation
    length = len(mods) # Total mods
    for i, modname in enumerate(mods): # For each mod in mod file list
        modinfo, fileinfo = _get_mod_info(modname, skiperrs, verbose, version, modloader) # Get curse mod info and file info

        manifest["files"].append({ # Append to modlist
            "projectID": modinfo["id"], # Project id
            "fileID": fileinfo["fileId"], # File id
            "downloadUrl": get(f"https://api.curseforge.com/v1/mods/{modinfo['id']}/files/{fileinfo['fileId']}", headers=HEADERS).json()["data"]["downloadUrl"], # Download url
            "required": True
        })
        
        if verbose: print(f"{modinfo['name']}: Done! ({i+1}/{length})") # Verbose output

        cache[modname] = modinfo["id"] # Add to cache

    if verbose: print("\nDone generating manifest.json!\n") # Done!

    with open("manifest.cache.json", "w+") as file: file.write(dumps(cache)) # Dump cache

    return manifest # Return the manifest dict

# Generate (the activation function)
def generate(*args, **kwargs) -> None:
    try: 
        manifest = dumps(_construct_manifest(*args, **kwargs)) # Dump generated manifest
    except TypeError:
        _handle_exception("Modpack name not set. Use --name to do that.") # Stupid
    except KeyboardInterrupt: # On interrupt
        print("\nAborted.\n")
        exit(0) # Stop
    
    with open("manifest.json", "w+") as file: file.write(manifest) # Write manifest to file

# That's it. Pizza time 🍕🍕🍕
# Made and commented through by G_cat101 :)