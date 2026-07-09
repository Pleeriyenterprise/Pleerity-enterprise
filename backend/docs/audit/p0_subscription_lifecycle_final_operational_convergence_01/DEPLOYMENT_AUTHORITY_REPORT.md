# Deployment Authority

```json
{
  "phase": 1,
  "expected_commit": "2c175d7ee8112c1cd2cfeeba5e00047cf2cd12bc",
  "verdict": "PASS",
  "backend": {
    "version_status": 200,
    "health_status": 200,
    "deployed_sha": "2c175d7ee8112c1cd2cfeeba5e00047cf2cd12bc",
    "sha_match": true
  },
  "frontend": {
    "homepage_status": 200,
    "bundle": "main.04ff376e.js",
    "bundle_sha256": "fbab9f5002982db9c1543ba4304f25231bf322003df5e7e01754d02a82e49e2d",
    "commit_in_bundle": false,
    "lifecycle_markers": {
      "lifecycle-keep-subscription": true,
      "resume_subscription": true,
      "billing-keep-subscription": true
    },
    "all_lifecycle_markers": true
  }
}
```
