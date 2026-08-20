import { useState } from 'react';

interface Props {
  userId: string;
  onUserChange: (userId: string) => void;
}

export function UserSelector({ userId, onUserChange }: Props) {
  const [input, setInput] = useState(userId);

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-gray-500">User:</label>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onBlur={() => onUserChange(input)}
        onKeyDown={(e) => e.key === 'Enter' && onUserChange(input)}
        className="border rounded px-2 py-1 text-sm w-40"
        placeholder="dev-user"
      />
    </div>
  );
}
