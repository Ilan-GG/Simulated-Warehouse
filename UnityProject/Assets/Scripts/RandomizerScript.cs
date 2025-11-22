using UnityEngine;
using Unity.AI.Navigation;

public class RandomizerScript : MonoBehaviour
{
    [Header("Prefabs")]
    public GameObject botPrefab;
    public GameObject shelfPrefab;
    public GameObject boxPrefab;

    [Header("Counts")]
    public int botCount = 5;
    public int shelfCount = 10;
    public int boxCount = 20;

    [Header("Spawn Area")]
    public Vector2 areaSize = new Vector2(50f, 50f); // Tamaño del plano (X,Z)
    public float yPos = 0f; // Altura donde instanciar objetos

    [Header("NavMesh")]
    public NavMeshSurface navMeshSurface;

    void Start()
    {
        GenerateObjects();
        BakeNavMesh();
    }

    void GenerateObjects()
    {
        SpawnObjects(botPrefab, botCount);
        SpawnObjects(shelfPrefab, shelfCount);
        SpawnObjects(boxPrefab, boxCount);
    }

    void SpawnObjects(GameObject prefab, int count)
    {
        for (int i = 0; i < count; i++)
        {
            Vector3 pos = GetRandomPosition();
            Instantiate(prefab, pos, Quaternion.identity);
        }
    }

    Vector3 GetRandomPosition()
    {
        int x = Random.Range(-(int)areaSize.x / 2, (int)areaSize.x / 2);
        int z = Random.Range(-(int)areaSize.y / 2, (int)areaSize.y / 2);

        return new Vector3(x, yPos, z);
    }

    void BakeNavMesh()
    {
        if (navMeshSurface != null)
        {
            navMeshSurface.BuildNavMesh();
        }
        else
        {
            Debug.LogWarning("NavMeshSurface no asignado.");
        }
    }
}
