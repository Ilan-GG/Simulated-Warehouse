using UnityEngine;
using UnityEngine.AI;
using System.Collections.Generic;

public class RobotScriptTest : MonoBehaviour
{
    public string targetTag = "Box";
    public string shelfTag = "Shelf";

    public Transform grabPoint;
    public float grabDistance = 2.0f;

    private NavMeshAgent agent;

    private GameObject currBox;
    private ShelfScript currShelf;
    private Transform currShelfSpot;

    private bool hasBox = false;
    private bool isPickingUp = false;

    // Logica de Busqueda

    public Vector2 areaSize = new Vector2(20f, 20f);

    private enum BotState { Searching, PickingUp, Delivering }
    private BotState state = BotState.Searching;

    private List<GameObject> knownBoxes = new List<GameObject>();

    void Start()
    {
        agent = GetComponent<NavMeshAgent>();
        RandomTrip();
    }

    void Update()
    {
        switch (state)
        {
            case BotState.Searching:
                RandomTrip();
                break;

            case BotState.PickingUp:
                if (currBox == null)
                {
                    FindClosestBox();
                    return;
                }
                agent.SetDestination(currBox.transform.position);
                break;

            case BotState.Delivering:
                if(currShelf == null)
                {
                    FindClosestShelf(); 
                    Debug.Log("Delivering...");
                }
                agent.SetDestination(currShelf.transform.position);
                DeliverBox();
                break;
        }
    }

    void RandomTrip()
    {
        if(agent.remainingDistance < 0.5f)
        {
            
            Debug.Log("Searching...");
            
            int x = Random.Range(-(int)areaSize.x / 2, (int)areaSize.x / 2);
            int z = Random.Range(-(int)areaSize.y / 2, (int)areaSize.y / 2);

            Vector3 RandomPos = new Vector3(x,0f,z);
            agent.SetDestination(RandomPos);
        }
    }

    void DeliverBox()
    {
        Vector3 deliveryPoint = new Vector3(currShelf.transform.position.x, 0.5f, currShelf.transform.position.z);
        float dist = Vector3.Distance(transform.position, deliveryPoint);

        if (dist < 1.5f)
        {
            Debug.Log("Dejando Caja");
            DropBox();
        }
    }


    void FindClosestBox()
    {
        Debug.Log("Picking Up Known Box...");

        float minDist = Mathf.Infinity;
        GameObject nearest = null;

        foreach (GameObject b in knownBoxes)
        {
            BoxScript bs = b.GetComponent<BoxScript>();

            // Filtros
            if (bs != null && (bs.isStored || bs.isAssigned))
                continue;

            float dist = Vector3.Distance(transform.position, b.transform.position);
            if (dist < minDist)
            {
                minDist = dist;
                nearest = b;
            }
        }

        currBox = nearest;

        if (currBox == null) {
            state = BotState.Searching;
        } else {
            BoxScript CurrBs = currBox.GetComponent<BoxScript>();
            CurrBs.isAssigned = true;
            isPickingUp = true;
            state = BotState.PickingUp;
        }
    }


    void FindClosestShelf()
    {
        GameObject[] shelves = GameObject.FindGameObjectsWithTag(shelfTag);

        float minDist = Mathf.Infinity;
        ShelfScript nearestShelf = null;
        Transform nearestSpot = null;

        foreach (GameObject s in shelves)
        {
            ShelfScript sc = s.GetComponent<ShelfScript>();
            Transform freeSpot = sc.GetFirstFreeSpot();

            if (freeSpot != null) // Solo considerar si tiene espacio
            {
                float dist = Vector3.Distance(transform.position, freeSpot.position);
                if (dist < minDist)
                {
                    minDist = dist;
                    nearestShelf = sc;
                    nearestSpot = freeSpot;
                }
            }
        }

        currShelf = nearestShelf;
        // currShelfSpot = null; // El spot NO se calcula aquí

    }
    
    private void OnTriggerEnter(Collider other)
    {
        if (hasBox) return;
        //if (currBox == null) return;

        if(other.CompareTag(targetTag))
        {
            if(!knownBoxes.Contains(other.gameObject)) 
            {
                knownBoxes.Add(other.gameObject);
                Debug.Log("Caja Encontrada");
            }
            if(!hasBox && !isPickingUp) 
            {
                BoxScript CurrBs = other.gameObject.GetComponent<BoxScript>();
                if(!CurrBs.isAssigned)
                {
                    CurrBs.isAssigned = true;
                    PickUpBox(other.gameObject); 
                }
                
            }
        }

        if (other.gameObject == currBox)
        {
            PickUpBox(other.gameObject);
        }
    }

    void PickUpBox(GameObject box)
    {
        Debug.Log("Caja agarrada: " + box.name);

        // Desactivar física
        if (box.TryGetComponent<Rigidbody>(out Rigidbody rb))
        {
            rb.isKinematic = true;
        }

        // Mover al punto de agarre
        box.transform.SetParent(grabPoint);
        box.transform.localPosition = Vector3.zero;
        box.transform.localRotation = Quaternion.identity;

        hasBox = true;
        currBox = null;
        isPickingUp = false;

        state = BotState.Delivering;
    }

    void DropBox()
    {
        if (currShelf != null)
            currShelfSpot = currShelf.GetFirstFreeSpot();

        if (currShelfSpot == null)
        {
            Debug.LogWarning("Ningún spot disponible al momento de dejar la caja. Rebuscando shelf...");
            hasBox = true;
            currShelf = null;
            FindClosestShelf();
            return;
        }

        Transform box = grabPoint.GetChild(0);

        // Marcar la caja como almacenada
        if (box.TryGetComponent<BoxScript>(out BoxScript bs))
            bs.isStored = true;

        // Colocar en shelf
        box.SetParent(currShelfSpot);
        box.localPosition = Vector3.zero;
        box.localRotation = Quaternion.identity;

        // Logica de Busqueda

        hasBox = false;
        currShelf = null;
        currShelfSpot = null;

        FindClosestBox();
    }


}
