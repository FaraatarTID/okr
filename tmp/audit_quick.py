import json
import re
import urllib.request
import urllib.error

def audit_requirements():
    req_file = "streamlit_app/requirements.txt"
    packages = []
    
    # Simple requirements parser for compiled pip-tools files
    with open(req_file, "r") as f:
        content = f.read()
        
    # Match package==version and skip comments / hashes
    matches = re.finditer(r"^([a-zA-Z0-9_\-]+)==([0-9\.\-a-zA-Z]+(post[0-9]+)?)", content, re.MULTILINE)
    for m in matches:
        packages.append((m.group(1), m.group(2)))
        
    print(f"Found {len(packages)} packages to audit.")
    
    vulnerable = []
    for pkg, ver in packages:
        # Query OSV API
        url = "https://api.osv.dev/v1/query"
        data = {
            "version": ver,
            "package": {
                "name": pkg.lower(),
                "ecosystem": "PyPI"
            }
        }
        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=req_data, 
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode("utf-8"))
                if "vulns" in res:
                    print(f"[VULNERABLE] {pkg}=={ver} has {len(res['vulns'])} vulnerabilities!")
                    for v in res["vulns"]:
                        print(f"  - {v['id']}: {v.get('summary', 'No summary')}")
                    vulnerable.append((pkg, ver, res["vulns"]))
        except urllib.error.HTTPError as e:
            print(f"Error querying {pkg}=={ver}: {e}")
            
    if not vulnerable:
        print("No vulnerabilities found in requirements.txt!")
    else:
        print(f"Total vulnerable packages: {len(vulnerable)}")

if __name__ == "__main__":
    audit_requirements()
