// Extensão "Rap de Anime e Mangá" para FreeBeat
const PLAYLIST_URL = 'https://raw.githubusercontent.com/escritor3/rap_anime/main/rap_anime/playlist.json';

module.exports = {
  id: 'rap_anime_repo',
  name: 'Rap de Anime & Mangá',
  version: '1.0.0',
  hasCatalog: true,

  async getCatalog(api) {
    const data = await api.httpGetJson(PLAYLIST_URL);
    return api.normalizeSongs(data);
  },

  async search(query, api) {
    const data = await api.httpGetJson(PLAYLIST_URL);
    const songs = api.normalizeSongs(data);
    const q = query.toLowerCase();
    return songs.filter(
      (s) =>
        s.titulo.toLowerCase().includes(q) ||
        (s.artista && s.artista.toLowerCase().includes(q)) ||
        (s.genero && s.genero.toLowerCase().includes(q))
    );
  },
};
