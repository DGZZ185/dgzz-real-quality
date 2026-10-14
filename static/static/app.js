const form = document.querySelector("#form");
const fileInput = document.querySelector("#file");
const fileTitle = document.querySelector("#file-title");
const fileSub = document.querySelector("#file-sub");
const statusBox = document.querySelector("#status");
const submit = document.querySelector("#submit");
const result = document.querySelector("#result");
const preview = document.querySelector("#preview");
const download = document.querySelector("#download");
const tiktokState = document.querySelector("#tiktok-state");
const connectTikTok = document.querySelector("#connect-tiktok");
const caption = document.querySelector("#caption");
const captionCount = document.querySelector("#caption-count");
const autoPost = document.querySelector("#auto-post");
const postStatus = document.querySelector("#post-status");
let processedBlob = null;
let tiktokConnected = false;

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileTitle.textContent = file ? file.name : "Escolha seu vídeo";
  fileSub.textContent = file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · pronto para processar` : "MP4, MOV, MKV ou WebM · limite inicial de 250 MB";
});

fetch("/api/status").then(r => r.json()).then(data => {
  statusBox.textContent = data.ffmpeg_available
    ? `Estúdio online · limite por arquivo: ${data.max_upload_mb} MB.`
    : "O servidor está no ar, mas o FFmpeg não foi encontrado. Instale o FFmpeg no servidor.";
  if (!data.ffmpeg_available) statusBox.classList.add("error");
}).catch(() => {
  statusBox.textContent = "Não foi possível consultar o servidor.";
  statusBox.classList.add("error");
});

async function refreshTikTokStatus() {
  try {
    const r = await fetch("/api/tiktok/status");
    const data = await r.json();
    tiktokConnected = Boolean(data.connected);
    tiktokState.textContent = tiktokConnected ? `Conectado${data.username ? ` como @${data.username}` : ""}` : "Conta do TikTok não conectada";
    connectTikTok.textContent = tiktokConnected ? "Reconectar TikTok ↗" : "Conectar TikTok ↗";
    autoPost.disabled = !(tiktokConnected && processedBlob);
    if (!data.configured) postStatus.textContent = "A integração precisa ser configurada pelo administrador com credenciais de desenvolvedor do TikTok.";
  } catch {
    tiktokState.textContent = "Não foi possível verificar a conexão";
  }
}
refreshTikTokStatus();
caption.addEventListener("input", () => captionCount.textContent = `${caption.value.length} / 2200`);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;
  const data = new FormData(form);
  data.set("sharpen", form.elements.sharpen.checked ? "true" : "false");
  submit.disabled = true;
  submit.querySelector("span").textContent = "PROCESSANDO…";
  result.hidden = true;
  statusBox.classList.remove("error");
  statusBox.textContent = "Enviando e processando. Vídeos longos, 4K e 120 FPS podem demorar vários minutos.";
  try {
    const response = await fetch("/api/process", { method: "POST", body: data });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Falha no processamento.");
    }
    const blob = await response.blob();
    processedBlob = blob;
    const url = URL.createObjectURL(blob);
    preview.src = url;
    download.href = url;
    result.hidden = false;
    autoPost.disabled = !tiktokConnected;
    statusBox.textContent = "Concluído! Seu vídeo está pronto para baixar.";
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    statusBox.textContent = `Erro: ${error.message}`;
    statusBox.classList.add("error");
  } finally {
    submit.disabled = false;
    submit.querySelector("span").textContent = "PROCESSAR VÍDEO";
  }
});


autoPost.addEventListener("click", async () => {
  if (!processedBlob || !tiktokConnected) return;
  autoPost.disabled = true;
  postStatus.textContent = "Enviando vídeo para o TikTok…";
  const data = new FormData();
  data.append("file", processedBlob, "dgzz-real-quality.mp4");
  data.append("caption", caption.value);
  try {
    const response = await fetch("/api/tiktok/publish", { method: "POST", body: data });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Não foi possível publicar.");
    postStatus.textContent = payload.message || "Solicitação enviada ao TikTok.";
  } catch (error) {
    postStatus.textContent = `Erro ao publicar: ${error.message}`;
  } finally {
    autoPost.disabled = !tiktokConnected || !processedBlob;
  }
});
