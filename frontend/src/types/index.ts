export interface Message {
  role: 'user' | 'ai';
  text: string;
  timestamp: string;
}

export interface ChatState {
  messages: Message[];
  loading: boolean;
  dark: boolean;
}

