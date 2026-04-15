"""Test: navigate to Google Travel and auto-handle consent."""
import asyncio, sys, os
sys.path.insert(0, "/home/azureuser/Ombra/backend")
os.environ["DISPLAY"] = ":1"

async def main():
    from computer_use import ComputerUseEngine
    engine = ComputerUseEngine()
    
    print("=== Testing navigate (should auto-handle consent) ===")
    result = await engine.navigate("https://www.google.com/travel/flights")
    print(f"Success: {result.get('success')}")
    print(f"URL: {result.get('url')}")
    print(f"Title: {result.get('title')}")
    print(f"Consent handled: {result.get('consent_auto_handled')}")
    
    elements = result.get("interactive_elements", [])
    print(f"\nInteractive elements: {len(elements)}")
    for el in elements[:15]:
        print(f"  <{el.get('tag')}> text={el.get('text','')!r} selector={el.get('selector','')!r}")
    
    await engine.close()
    print("\nDone!")

asyncio.run(main())
