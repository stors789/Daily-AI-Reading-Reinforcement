from desktop_adapters import DesktopConfigAdapter
c = DesktopConfigAdapter()
config = c.load()
print("Loaded:", config)
config["api_key"] = "test-key"
c.save(config)

c2 = DesktopConfigAdapter()
config2 = c2.load()
print("Reloaded:", config2)
