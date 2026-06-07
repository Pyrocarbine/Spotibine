export default function SequenceList({ sequences, selectedId, onSelect, onDelete }) {
  if (!sequences.length) {
    return <p className="muted">No sequences saved yet.</p>;
  }

  return (
    <ul className="sequence-list">
      {sequences.map((sequence) => {
        const isSelected = sequence.id === selectedId;
        return (
          <li key={sequence.id} className={isSelected ? "sequence selected" : "sequence"}>
            <button className="select-button" onClick={() => onSelect(sequence.id)}>
              {sequence.presentation}
            </button>
            <button className="delete-button" onClick={() => onDelete(sequence.id)}>
              Delete
            </button>
          </li>
        );
      })}
    </ul>
  );
}
