import cv2
import os


def list_cameras():
    """
    Lista as câmaras disponíveis no sistema Linux utilizando a interface V4L2.
    
    Retorna:
        list: Uma lista de tuplos, onde cada tuplo contém (índice/dispositivo, nome da câmara)
    """
    cameras = []  # Lista para armazenar as câmaras encontradas
    
    print("Procura câmaras usando V4L2...")  # Mensagem informativa sobre a verificação de câmaras
    
    # Verifica os caminhos comuns dos dispositivos V4L2 (Video4Linux)
    v4l2_devices = [
        '/dev/video0', '/dev/video1', '/dev/video2', '/dev/video3',
        '/dev/video4', '/dev/video5', '/dev/video6', '/dev/video7'
    ]
    
    # Itera sobre cada caminho de dispositivo possível
    for device_path in v4l2_devices:
        if os.path.exists(device_path):  # Verifica se o dispositivo existe no sistema
            try:
                # Tenta abrir a câmara com o backend V4L2
                cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
                if cap.isOpened():  # Verifica se a câmara foi aberta com sucesso
                    ret, frame = cap.read()  # Tenta ler um frame para validar a câmara
                    if ret and frame is not None:  # Se a leitura foi bem-sucedida
                        # Obtém as propriedades da câmara
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))   # Largura da imagem
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) # Altura da imagem
                        fps = cap.get(cv2.CAP_PROP_FPS)                  # Taxa de frames por segundo
                        
                        # Cria uma descrição da câmara
                        camera_name = f"{device_path} ({width}x{height}, {fps:.1f} FPS)"
                        cameras.append((device_path, camera_name))  # Adiciona à lista
                        print(f"Found: {camera_name}")  # Mostra a câmara encontrada
                    
                    cap.release()  # Liberta os recursos da câmara
                    cv2.destroyAllWindows()  # Fecha quaisquer janelas abertas pelo OpenCV
            except Exception as e:
                print(f"Teste de erro {device_path}: {e}")  # Mostra erro ao testar o dispositivo
                continue  # Continua para o próximo dispositivo
    
    # Fallback: se nenhuma câmara foi encontrada, tenta usar índices numéricos
    if not cameras:
        print("Tentar índices numéricos com V4L2...")
        for index in range(0, 10):  # Testa os primeiros 10 índices de câmara
            try:
                cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
                if cap.isOpened():  # Se a câmara foi aberta com sucesso
                    ret, frame = cap.read()  # Tenta ler um frame
                    if ret and frame is not None:  # Se a leitura foi bem-sucedida
                        # Obtém as propriedades da câmara
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        # Cria uma descrição da câmara
                        camera_name = f"Câmara {index} ({width}x{height}, {fps:.1f} FPS)"
                        cameras.append((index, camera_name))  # Adiciona à lista
                        print(f"Found: {camera_name}")
                    
                    cap.release()  # Liberta os recursos da câmara
                    cv2.destroyAllWindows()  # Fecha janelas do OpenCV
            except Exception as e:
                print(f"Erro ao testar a câmara {index}: {e}")
                continue
    
    return cameras  # Retorna a lista de câmaras encontradas


def select_camera():
    """
    Permite ao utilizador selecionar qual câmara utilizar.
    
    Retorna:
        int/str or None: O índice da câmara selecionada, ou None se não houver câmara
    """
    cameras = list_cameras()  # Obtém a lista de câmaras disponíveis
    
    # Se não houver câmaras, mostra instruções de resolução de problemas
    if not cameras:
        print("\nNenhuma câmara encontrada!")
        print("\nEtapas de resolução de problemas:")
        print("1. Certifique-se de que a sua webcam está ligada")
        print("2. Verifique se o V4L2 está instalado: sudo apt install v4l-utils")
        print("3. Listar dispositivos: v4l2-ctl --list-devices")
        print("4. Verifique as permissões: ls -la /dev/video*")
        return None
    
    # Mostra as câmaras encontradas
    print(f"\n✅ Found {len(cameras)} camera(s):")
    for idx, (cam_index, cam_name) in enumerate(cameras):
        print(f"{idx + 1}. {cam_name}")
    
    # Se houver apenas uma câmara, seleciona-a automaticamente
    if len(cameras) == 1:
        print(f"\nUtilizando a única câmara disponível: {cameras[0][1]}")
        return cameras[0][0]
    
    # Loop para obter uma seleção válida do utilizador
    while True:
        try:
            choice = input(f"\nSelecione uma câmara (1-{len(cameras)}) ou 'q' para sair: ")
            if choice.lower() == 'q':  # Permite ao utilizador sair
                return None
            choice = int(choice)  # Converte a entrada para número inteiro
            if 1 <= choice <= len(cameras):  # Verifica se a escolha é válida
                selected_index = cameras[choice - 1][0]  # Obtém o índice da câmara selecionada
                print(f"Selected: {cameras[choice - 1][1]}")  # Mostra a câmara selecionada
                return selected_index
            print("Opção inválida. Por favor tente outra vez.")  # Mensagem de erro para escolha inválida
        except ValueError:
            print("Insira um número.")  # Mensagem de erro para entrada não numérica