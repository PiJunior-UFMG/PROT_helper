import React, { useState,useRef, useEffect } from 'react';
import { Send, User, Plus, Bot } from 'lucide-react';

export default function App() {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/whatsapp';

  const [clients, setClients] = useState([
    { id: '1', name: 'Cliente A', phone: 'whatsapp:+5531999990001' },
    { id: '2', name: 'Cliente B', phone: 'whatsapp:+5531999990002' },
  ]);

  const [messages, setMessages] = useState({});
  const [activeClientId, setActiveClientId] = useState(null);
  const [inputText, setInputText] = useState('');
  const [newClientPhone, setNewClientPhone] = useState('');

  const activeClient = clients.find(c => c.id === activeClientId);
  const activeMessages = activeClient && messages[activeClient.phone] ? messages[activeClient.phone] : [];


  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeMessages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || !activeClient) return;

    const userMessage = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Atualiza a tela com a mensagem enviada
    setMessages(prev => ({
      ...prev,
      [activeClient.phone]: [...(prev[activeClient.phone] || []), userMessage]
    }));
    
    setInputText('');

    // 1. Emula perfeitamente o payload do Twilio (Form Data)
    const formData = new URLSearchParams();
    formData.append('From', activeClient.phone);
    formData.append('Body', userMessage.text);
    // Você pode adicionar ProfileName, WaId, etc., se sua API usar no futuro

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
      });

      // 2. Recebe e faz o parse do XML (TwiML)
      const xmlText = await response.text();
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(xmlText, "text/xml");
      
      // Busca todas as tags <Body> dentro do XML de resposta
      const bodyNodes = xmlDoc.getElementsByTagName("Body");
      
      if (bodyNodes.length > 0) {
        // O Twilio pode enviar múltiplas mensagens de uma vez usando vários <Message><Body>
        const newBotMessages = Array.from(bodyNodes).map((node, index) => ({
          id: Date.now().toString() + index,
          text: node.textContent,
          sender: 'bot',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }));

        setMessages(prev => ({
          ...prev,
          [activeClient.phone]: [...(prev[activeClient.phone] || []), ...newBotMessages]
        }));
      }
    } catch (error) {
      console.error("Erro ao conectar com a API:", error);
    }
  };

  const handleAddClient = (e) => {
    e.preventDefault();
    if (!newClientPhone.trim()) return;
    
    // O Twilio costuma enviar os números do WhatsApp com este prefixo
    const phoneFormatted = newClientPhone.startsWith('whatsapp:') 
      ? newClientPhone 
      : `whatsapp:${newClientPhone}`;

    const newClient = {
      id: Date.now().toString(),
      name: `Cliente ${clients.length + 1}`,
      phone: phoneFormatted
    };
    
    setClients([...clients, newClient]);
    setNewClientPhone('');
  };

  return (
    <div className="h-screen w-full flex items-center justify-center p-4">
      <div className="w-full max-w-6xl h-[90vh] bg-white rounded-lg shadow-2xl overflow-hidden flex border border-gray-300">
        
        {/* SIDEBAR */}
        <div className="w-1/3 bg-gray-50 border-r border-gray-200 flex flex-col">
          <div className="h-16 bg-gray-100 flex items-center px-4 font-semibold text-gray-700 border-b border-gray-200">
            Simulador TwiML
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {clients.map(client => (
              <div 
                key={client.id}
                onClick={() => setActiveClientId(client.id)}
                className={`flex items-center gap-3 p-4 cursor-pointer border-b border-gray-100 transition-colors ${
                  activeClientId === client.id ? 'bg-blue-50' : 'hover:bg-gray-100'
                }`}
              >
                <div className="w-12 h-12 bg-gray-300 rounded-full flex items-center justify-center text-gray-600 shrink-0">
                  <User size={24} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-gray-900 truncate">{client.name}</h3>
                  <p className="text-sm text-gray-500 truncate">{client.phone}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 bg-white border-t border-gray-200">
            <form onSubmit={handleAddClient} className="flex gap-2">
              <input 
                type="text" 
                placeholder="+5511999990000" 
                className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                value={newClientPhone}
                onChange={(e) => setNewClientPhone(e.target.value)}
              />
              <button type="submit" className="p-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                <Plus size={20} />
              </button>
            </form>
          </div>
        </div>

        {/* ÁREA DE CHAT */}
        <div className="flex-1 flex flex-col bg-[#efeae2]">
          {activeClient ? (
            <>
              {/* Header */}
              <div className="h-16 bg-gray-100 flex items-center px-4 border-b border-gray-200 gap-3">
                <div className="w-10 h-10 bg-green-600 rounded-full flex items-center justify-center text-white shrink-0">
                  <Bot size={20} />
                </div>
                <div className="flex flex-col">
                  <span className="font-semibold text-gray-800">Seu Chatbot (Twilio Webhook)</span>
                  <span className="text-xs text-gray-500">
                    Enviando como: <strong className="text-gray-700">{activeClient.phone}</strong>
                  </span>
                </div>
              </div>

              {/* Mensagens */}
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
                {activeMessages.map(msg => (
                  <div 
                    key={msg.id} 
                    className={`max-w-[70%] min-w-[90px] rounded-lg px-3 pt-2 pb-1.5 shadow-sm flex flex-col ${
                      msg.sender === 'user' 
                        ? 'bg-[#d9fdd3] self-end rounded-tr-none' 
                        : 'bg-white self-start rounded-tl-none'
                    }`}
                  >
                    <p className="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap break-words">
                      {msg.text}
                    </p>
                    <span className="text-[10px] text-gray-500 self-end mt-1">
                      {msg.timestamp}
                    </span>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
              
              {/* Input */}
              <div className="bg-gray-100 p-3 border-t border-gray-200">
                <form onSubmit={handleSendMessage} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder="Digite a mensagem..."
                    className="flex-1 py-3 px-4 rounded-lg border-none focus:outline-none focus:ring-1 focus:ring-green-500 shadow-sm"
                  />
                  <button 
                    type="submit"
                    disabled={!inputText.trim()}
                    className="p-3 bg-green-600 text-white rounded-full hover:bg-green-700 disabled:opacity-50"
                  >
                    <Send size={20} className="ml-1" />
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500 gap-4">
              <User size={64} className="text-gray-300" />
              <p>Selecione um perfil de teste na lateral.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}