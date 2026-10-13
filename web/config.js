// Public app config. The token below is READ-ONLY and server-enforced
// (verified: SELECTs succeed, writes return BLOCKED) — published by design
// so the viewing tier needs no login; revoked after the demo window.
// Dev override: localStorage keys aps_turso_url / aps_turso_token.
window.APS_CONFIG = {
  tursoUrl: "https://aps-rescue-sxchen210.aws-us-west-2.turso.io",
  tursoToken: "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicm8iLCJpYXQiOjE3OTE4NTUzMTYsImlkIjoiMDFhMTJjMGUtMDEwMS03OWJlLWI2MzgtYzcyYjhhMWMyMjE2Iiwia2lkIjoiZkR0Zmp4eHpyaHVoMVRqTncxY01TYktRdDVuZWN5aG5FZFU2U0I3R2JQMCIsInJpZCI6ImQ5Yjk5ZTIwLTQ1NDYtNGE1YS1iYjQ0LWNjOGFhM2Y2MDNiNyJ9.T5oU3gwLcrOd3I5l1T-Ed8EUw8cPM6BOuORDhNiY1fbntsiELn9IzVF-gd3ZaHxFojLWu26LKoVBNMVmAHa1Dg",
  backendUrl: "https://aps-rescue-demo.fly.dev",
};
