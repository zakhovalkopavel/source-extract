import axios from 'axios';

const baseURL = import.meta.env.VITE_SE_API_URL || '/source-extractor/api/v1';

export const seClient = axios.create({
  baseURL,
  headers: { Accept: 'application/json' },
});

export type CommandParam = {
  name: string;
  type: string;
  description?: string;
  default?: unknown;
  required?: boolean;
  choices?: unknown[] | null;
  group?: string;
  advanced?: boolean;
  positional?: boolean;
};

export type CommandSpecDto = {
  id: string;
  title: string;
  description: string;
  family: string;
  adapterId?: string | null;
  params: CommandParam[];
};

export type JobDto = {
  id: string;
  commandId: string;
  state: string;
  log: string[];
  exitCode?: number | null;
  error?: string | null;
};
