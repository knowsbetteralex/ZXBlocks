// Persistence is independent of Blockly and the UI so writes cannot race.
export async function request(path, body) {
  const response = await fetch(path, body === undefined ? {cache: 'no-store'} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw Object.assign(new Error(result.error?.message ?? 'Не удалось выполнить действие'), result.error, {status: response.status});
  return result;
}

export const recoveryKey = id => `zxblocks.draft.v2.${id}`;

export class ProjectSession {
  constructor(record, capture, {send = request, storage = null, changed = () => {}} = {}) {
    this.id = record.id;
    this.revision = record.revision;
    this.saved = JSON.stringify(record.document);
    this.capture = capture;
    this.send = send;
    this.storage = storage;
    this.changed = changed;
    this.pending = null;
    this.conflict = false;
    this.error = null;
  }

  get dirty() { return JSON.stringify(this.capture()) !== this.saved; }

  remember() {
    try {
      if (this.dirty) this.storage?.setItem(recoveryKey(this.id), JSON.stringify({revision: this.revision, document: this.capture()}));
      else this.storage?.removeItem(recoveryKey(this.id));
    } catch { /* Server saving also works when browser storage is full/disabled. */ }
    this.changed(this);
  }

  async save() {
    if (this.pending) return this.pending;
    this.pending = this.writeChanges();
    this.changed(this);
    try { await this.pending; }
    finally { this.pending = null; this.changed(this); }
  }

  async writeChanges() {
    try {
      while (this.dirty) {
        if (this.conflict) throw new Error('Проект изменён в другой вкладке. Откройте его заново или создайте копию через меню.');
        const document = this.capture();
        const saved = JSON.stringify(document);
        const record = await this.send(`/api/projects/${this.id}/save`, {revision: this.revision, document});
        this.revision = record.revision;
        this.saved = saved;
        this.error = null;
        this.remember();
      }
    } catch (error) {
      this.error = error;
      this.conflict = error.status === 409 || this.conflict;
      this.remember();
      throw error;
    }
  }
}
