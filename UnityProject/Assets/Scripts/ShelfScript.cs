using UnityEngine;
using System.Collections.Generic;

public class ShelfScript : MonoBehaviour
{
    public List<Transform> positions = new List<Transform>();

    void Awake()
    {
        // Busca los 5 hijos llamados Pos1, Pos2...

        /*
        positions.Clear();
        for (int i = 1; i <= 5; i++)
        {
            Transform pos = transform.Find("Pos" + i);
            if (pos != null)
                positions.Add(pos);
        }
        */
    }

    public Transform GetFirstFreeSpot()
    {
        foreach (Transform pos in positions)
        {
            if (pos.childCount == 0) // Si está libre
                return pos;
        }
        return null; // Todo lleno
    }
}
