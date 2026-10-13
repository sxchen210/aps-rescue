// Public app config. tursoToken must be a READ-ONLY token (it is published by
// design); until one is minted it stays empty and the app reports the live
// database as unreachable. Dev override: set localStorage keys
// aps_turso_url / aps_turso_token in the browser console.
window.APS_CONFIG = {
  tursoUrl: "https://aps-rescue-sxchen210.aws-us-west-2.turso.io",
  tursoToken: "",
};
